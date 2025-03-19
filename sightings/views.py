import uuid
from warnings import filters
from django.shortcuts import render

# Create your views here.
# sightings/views.py

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import rest_framework as django_filters
from django.db.models import Q, Count
from datetime import datetime, timedelta
from django.utils import timezone

from accounts import models
from .models import Sighting
from .serializers import SightingSerializer
from deepface import DeepFace
import numpy as np
from .services import NotificationService, SightingService
from blockchain.services import BlockchainService
from missing_persons.models import MissingPerson
import tempfile
import os
from math import radians, sin, cos, sqrt, asin
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser


# import face_recognition

# First, create a filter set for Sighting
class SightingFilter(django_filters.FilterSet):
    start_date = django_filters.DateTimeFilter(field_name='timestamp', lookup_expr='gte')
    end_date = django_filters.DateTimeFilter(field_name='timestamp', lookup_expr='lte')
    location = django_filters.CharFilter(lookup_expr='icontains')
    verification_status = django_filters.ChoiceFilter(choices=Sighting.VERIFICATION_STATUS)
    confidence_level = django_filters.ChoiceFilter(choices=Sighting.CONFIDENCE_LEVELS)
    location_type = django_filters.ChoiceFilter(choices=Sighting.LOCATION_TYPES)
    crowd_density = django_filters.ChoiceFilter(choices=Sighting.CROWD_DENSITY)
    companions = django_filters.ChoiceFilter(choices=Sighting.COMPANION_TYPES)
    confidence_level_numeric_min = django_filters.NumberFilter(field_name='confidence_level_numeric', lookup_expr='gte')
    confidence_level_numeric_max = django_filters.NumberFilter(field_name='confidence_level_numeric', lookup_expr='lte')
    willing_to_contact = django_filters.BooleanFilter()
    has_photo = django_filters.BooleanFilter(field_name='photo', lookup_expr='isnull', exclude=True)
    missing_person_name = django_filters.CharFilter(field_name='missing_person__name', lookup_expr='icontains')
    reporter_name = django_filters.CharFilter(method='filter_reporter_name')
    distance = django_filters.NumberFilter(method='filter_by_distance')
    latitude = django_filters.NumberFilter()
    longitude = django_filters.NumberFilter()
    
    def filter_reporter_name(self, queryset, name, value):
        return queryset.filter(
            Q(reporter__first_name__icontains=value) |
            Q(reporter__last_name__icontains=value)
        )
    
    def filter_by_distance(self, queryset, name, value):
        """Filter sightings within specified kilometers of given lat/long"""
        lat = self.data.get('latitude')
        lon = self.data.get('longitude')
        if lat and lon and value:
            from math import radians, sin, cos, sqrt, asin
            
            lat, lon = float(lat), float(lon)
            radius = 6371  # Earth's radius in kilometers

            # Haversine formula
            queryset = queryset.extra(
                select={
                    'distance': f"""
                    {radius} * 2 * ASIN(
                        SQRT(
                            POWER(SIN(RADIANS({lat} - ABS(latitude)) / 2), 2) +
                            COS(RADIANS({lat})) * 
                            COS(RADIANS(ABS(latitude))) * 
                            POWER(SIN(RADIANS({lon} - longitude) / 2), 2)
                        )
                    )
                    """
                }
            ).filter(distance__lte=value)
        return queryset

    class Meta:
        model = Sighting
        fields = [
            'verification_status', 'confidence_level', 'location_type',
            'crowd_density', 'companions', 'willing_to_contact',
            'missing_person', 'reporter'
        ]

class SightingViewSet(viewsets.ModelViewSet):
    queryset = Sighting.objects.all().order_by('-timestamp')
    serializer_class = SightingSerializer
    filter_backends = [
        django_filters.DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter
    ]
    filterset_class = SightingFilter
    search_fields = [
        'description', 'location', 'location_details', 'wearing',
        'observed_behavior', 'missing_person__name'
    ]
    ordering_fields = [
        'timestamp', 'created_at', 'confidence_level_numeric',
        'verification_status'
    ]

    def get_queryset(self):
        """
        Get queryset based on user role and permissions
        """
        queryset = Sighting.objects.all().order_by('-timestamp')
        
        # If user is not authenticated, return empty queryset
        if not self.request.user.is_authenticated:
            return Sighting.objects.none()

        # If user is staff/admin, show all sightings
        if self.request.user.is_staff or self.request.user.role == 'ADMIN':
            return queryset
            
        # For NGOs and Law Enforcement, show sightings in their area
        if self.request.user.role in ['NGO', 'LAW_ENFORCEMENT']:
            if self.request.user.latitude and self.request.user.longitude:
                nearby_sightings = self.filter_by_distance(
                    queryset,
                    self.request.user.latitude,
                    self.request.user.longitude,
                    radius_km=50  # Configurable radius
                )
                return nearby_sightings
            return queryset
            
        # For regular users, show their own sightings and related sightings
        return queryset.filter(
            Q(reporter=self.request.user) |  # Their own sightings
            Q(missing_person__reporter=self.request.user) |  # Sightings of their reported missing persons
            Q(missing_person__family_group__members=self.request.user)  # Family group sightings
        ).distinct()

    def filter_by_distance(self, queryset, lat, lon, radius_km):
        """Filter queryset by distance from given coordinates"""
        from math import radians, sin, cos, sqrt, asin
        
        radius = 6371  # Earth's radius in kilometers

        # Haversine formula
        queryset = queryset.extra(
            select={
                'distance': f"""
                {radius} * 2 * ASIN(
                    SQRT(
                        POWER(SIN(RADIANS({lat} - ABS(latitude)) / 2), 2) +
                        COS(RADIANS({lat})) * 
                        COS(RADIANS(ABS(latitude))) * 
                        POWER(SIN(RADIANS({lon} - longitude) / 2), 2)
                    )
                )
                """
            }
        ).filter(
            latitude__isnull=False,
            longitude__isnull=False
        )
        
        if radius_km:
            queryset = queryset.extra(
                where=[f"""
                    {radius} * 2 * ASIN(
                        SQRT(
                            POWER(SIN(RADIANS({lat} - ABS(latitude)) / 2), 2) +
                            COS(RADIANS({lat})) * 
                            COS(RADIANS(ABS(latitude))) * 
                            POWER(SIN(RADIANS({lon} - longitude) / 2), 2)
                        )
                    ) <= %s
                """],
                params=[radius_km]
            )
        
        return queryset.order_by('distance')

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        
        # Get page size from query params or use default
        page_size = int(request.query_params.get('page_size', 10))
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
        else:
            serializer = self.get_serializer(queryset, many=True)
            response = Response(serializer.data)

        # Add summary statistics
        stats = {
            'total_count': queryset.count(),
            'verified_count': queryset.filter(verification_status='VERIFIED').count(),
            'pending_count': queryset.filter(verification_status='PENDING').count(),
            'with_photo_count': queryset.exclude(photo='').count(),
            'high_confidence_count': queryset.filter(confidence_level='HIGH').count(),
            'by_location_type': {
                'indoor': queryset.filter(location_type='INDOOR').count(),
                'outdoor': queryset.filter(location_type='OUTDOOR').count(),
                'vehicle': queryset.filter(location_type='VEHICLE').count(),
                'public_transport': queryset.filter(location_type='PUBLIC_TRANSPORT').count(),
            },
            'by_crowd_density': {
                'low': queryset.filter(crowd_density='LOW').count(),
                'medium': queryset.filter(crowd_density='MEDIUM').count(),
                'high': queryset.filter(crowd_density='HIGH').count(),
            }
        }
        
        if isinstance(response.data, dict):
            response.data['statistics'] = stats
            response.data['page_size'] = page_size
        else:
            response.data = {
                'results': response.data,
                'statistics': stats,
                'page_size': page_size
            }
            
        return response

    # Add pagination settings
    from rest_framework.pagination import PageNumberPagination
    
    class StandardResultsSetPagination(PageNumberPagination):
        page_size = 10
        page_size_query_param = 'page_size'
        max_page_size = 100
    
    pagination_class = StandardResultsSetPagination

    def get_permissions(self):
        """
        Allow anonymous users to create sightings,
        but require authentication for other actions
        """
        if self.action == 'create':
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def calculate_distance(self, lat1, lon1, lat2, lon2):
        """
        Calculate the great circle distance between two points 
        on the earth (specified in decimal degrees)
        """
        # Convert decimal degrees to radians
        lat1, lon1, lat2, lon2 = map(float, [lat1, lon1, lat2, lon2])
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        r = 6371  # Radius of earth in kilometers
        return c * r

    def create(self, request, *args, **kwargs):
        # Convert string 'true'/'false' to boolean for willing_to_contact
        # if 'willing_to_contact' in request.data:
        #     request.data._mutable = True
        #     request.data['willing_to_contact'] = request.data['willing_to_contact'].lower() == 'true'
        #     request.data._mutable = False

        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        print(f"data :{request.data.get('missing_person')}")
        # Handle case where no missing person exists but photo is provided
        missing_person_id = request.data.get('missing_person')
        if not missing_person_id and 'photo' in request.FILES:
            temp_missing_person = MissingPerson.objects.create(
                name="Unidentified Person",
                case_number=f"TEMP-{uuid.uuid4().hex[:8]}",
                status="MISSING",
                last_seen_location=request.data.get('location', 'Unknown'),
                last_seen_date=timezone.now(),
                reporter=request.user if request.user.is_authenticated else None,
                age_when_missing=0,  # Default value for unidentified persons
                gender='U',    # Default value
                height=0,           # Default value
                weight=0,           # Default value
                complexion='UNKNOWN' # Default value
            )
            serializer.validated_data['missing_person'] = temp_missing_person

        self.perform_create(serializer)
        sighting = serializer.instance

        # Process sighting (e.g., facial recognition)
        sighting_service = SightingService()
        sighting_service.process_sighting(sighting)
        
        # Find nearby entities
        notification_service = NotificationService()
        nearby_entities = None
        if sighting.latitude and sighting.longitude:
            nearby_entities = notification_service.find_nearby_entities(
                sighting.latitude, 
                sighting.longitude
            )
        notification_service.notify_entities(sighting, nearby_entities)
        
        headers = self.get_success_headers(serializer.data)
        response_data = serializer.data
        if nearby_entities:
            response_data['nearby_entities'] = {
                'ngos': [{'id': e['user'].id, 'distance': e['distance']} for e in nearby_entities['ngos']],
                'police': [{'id': e['user'].id, 'distance': e['distance']} for e in nearby_entities['police']]
            }
            
        return Response(response_data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        return serializer.save()

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')

    def process_facial_recognition(self, sighting):
        try:
            # Compare sighting photo with missing person's photo
            result = DeepFace.verify(
                sighting.photo.path,
                sighting.missing_person.recent_photo.path,
                model_name='VGG-Face'
            )
            
            # Update confidence and potentially status
            sighting.facial_match_confidence = result.get('distance', 0)
            if result.get('verified', False):
                sighting.confidence_level = 'HIGH'
                sighting.verification_status = 'VERIFIED'
                
                # Update missing person status if confidence is high
                if sighting.facial_match_confidence > 0.8:
                    missing_person = sighting.missing_person
                    missing_person.status = 'FOUND'
                    missing_person.save()
            
            sighting.save()
        except Exception as e:
            print(f"Error in facial recognition: {str(e)}")

    @action(detail=False, methods=['GET'])
    def nearby(self, request):
        """Get sightings near a specific location"""
        try:
            lat = float(request.query_params.get('latitude'))
            lon = float(request.query_params.get('longitude'))
            radius = float(request.query_params.get('radius', 2.0))  # km
            
            # Get sightings within radius using Haversine formula
            queryset = self.get_queryset().filter(
                latitude__isnull=False,
                longitude__isnull=False
            )
            
            nearby_sightings = []
            for sighting in queryset:
                try:
                    distance = self.calculate_distance(
                        lat, lon,
                        float(sighting.latitude),
                        float(sighting.longitude)
                    )
                    if distance <= radius:
                        sighting.distance = distance
                        nearby_sightings.append(sighting)
                except (ValueError, TypeError) as e:
                    print(f"Error calculating distance for sighting {sighting.id}: {str(e)}")
                    continue
            
            # Sort by distance
            nearby_sightings.sort(key=lambda x: x.distance)
            
            serializer = self.get_serializer(nearby_sightings, many=True)
            return Response(serializer.data)
        except ValueError:
            return Response(
                {'error': 'Invalid coordinates or radius'},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['GET'])
    def recent(self, request):
        """Get recent sightings, optionally filtered by missing person"""
        missing_person_id = request.query_params.get('missing_person_id')
        days = int(request.query_params.get('days', 7))
        
        queryset = self.get_queryset().filter(
            timestamp__gte=timezone.now() - timezone.timedelta(days=days)
        )
        
        if missing_person_id:
            queryset = queryset.filter(missing_person_id=missing_person_id)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        sighting = self.get_object()
        status = request.data.get('verification_status')
        notes = request.data.get('verification_notes', '')

        if status not in dict(Sighting.VERIFICATION_STATUS):
            return Response({'error': 'Invalid status'}, status=status.HTTP_400_BAD_REQUEST)

        sighting.verification_status = status
        sighting.verification_notes = notes
        sighting.verified_by = request.user
        sighting.save()

        sighting_service = SightingService()
        sighting_service.update_missing_person_status(sighting)
        sighting_service.notify_relevant_parties(sighting)

        serializer = self.get_serializer(sighting)
        return Response(serializer.data)

    def haversine_distance(self, lat1, lon1, lat2, lon2):
        lat1, lon1, lat2, lon2 = map(radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        r = 6371  # Radius of earth in kilometers
        return c * r    
    
    @action(detail=False, methods=['get'])
    def analytics(self, request):
        """Get analytics for all sightings without restrictions"""
        try:
            # Use all sightings without filtering by user permissions
            queryset = Sighting.objects.all()
            
            # Get time period from params (optional)
            days = request.query_params.get('days')
            if days:
                queryset = queryset.filter(
                    timestamp__gte=timezone.now() - timedelta(days=int(days))
                )
            
            # Get missing person filter (optional)
            missing_person_id = request.query_params.get('missing_person_id')
            if missing_person_id:
                queryset = queryset.filter(missing_person_id=missing_person_id)

            # Compute analytics for all sightings
            data = {
                'total_sightings': queryset.count(),
                'by_status': queryset.values('verification_status').annotate(
                    count=Count('id', distinct=True)  # Add distinct=True
                ),
                'by_confidence': queryset.values('confidence_level').annotate(
                    count=Count('id', distinct=True)
                ),
                'by_location_type': queryset.values('location_type').annotate(
                    count=Count('id', distinct=True)
                ),
                'by_crowd_density': queryset.values('crowd_density').annotate(
                    count=Count('id', distinct=True)
                ),
                'by_companions': queryset.values('companions').annotate(
                    count=Count('id', distinct=True)
                ),
                'with_photo': queryset.exclude(photo='').count(),
                'willing_to_contact': queryset.filter(willing_to_contact=True).count(),
                'time_distribution': {
                    'last_24h': queryset.filter(
                        timestamp__gte=timezone.now() - timedelta(days=1)
                    ).count(),
                    'last_week': queryset.filter(
                        timestamp__gte=timezone.now() - timedelta(days=7)
                    ).count(),
                    'last_month': queryset.filter(
                        timestamp__gte=timezone.now() - timedelta(days=30)
                    ).count()
                },
                'heatmap_data': [
                    {
                        'lat': float(s.latitude),
                        'lng': float(s.longitude),
                        'count': 1,
                        'location': s.location  # Add location name
                    }
                    for s in queryset.filter(
                        latitude__isnull=False,
                        longitude__isnull=False
                    )
                ],
                'verification_rate': {
                    'verified': queryset.filter(verification_status='VERIFIED').count(),
                    'pending': queryset.filter(verification_status='PENDING').count(),
                    'rejected': queryset.filter(verification_status='REJECTED').count()
                },
                'confidence_levels': {
                    'high': queryset.filter(confidence_level='HIGH').count(),
                    'medium': queryset.filter(confidence_level='MEDIUM').count(),
                    'low': queryset.filter(confidence_level='LOW').count()
                },
                # Add more detailed statistics
                'by_location': queryset.values('location').annotate(
                    count=Count('id', distinct=True)
                ),
                'by_reporter': queryset.values(
                    'reporter__username',
                    'reporter__first_name',
                    'reporter__last_name'
                ).annotate(
                    count=Count('id', distinct=True)
                ),
                'by_missing_person': queryset.values(
                    'missing_person__name',
                    'missing_person__case_number'
                ).annotate(
                    count=Count('id', distinct=True)
                ),
                'timeline': queryset.values('timestamp__date').annotate(
                    count=Count('id', distinct=True)
                ).order_by('timestamp__date')
            }

            return Response(data)

        except Exception as e:
            import traceback
            print(traceback.format_exc())  # Log the full error
            return Response(
                {'error': f'Error generating analytics: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )