from warnings import filters
from django.shortcuts import render

# Create your views here.
# sightings/views.py

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from .models import Sighting
from .serializers import SightingSerializer
from deepface import DeepFace
import numpy as np
from .services import SightingService
from blockchain.services import BlockchainService
from django.db.models import Q
from django.utils import timezone
from missing_persons.models import MissingPerson
import tempfile
import os
from math import radians, sin, cos, sqrt, asin
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

# import face_recognition

class SightingViewSet(viewsets.ModelViewSet):
    queryset = Sighting.objects.all()
    serializer_class = SightingSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['verification_status', 'confidence_level']
    search_fields = ['missing_person__name', 'location', 'description']
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    
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
    
    def get_queryset(self):
            queryset = Sighting.objects.all()
            if not self.request.user.is_staff:
                family_groups = self.request.user.families.all()
                queryset = queryset.filter(
                    Q(reporter=self.request.user) | Q(missing_person__family_group__in=family_groups)
                )
            return queryset
    
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

    def perform_create(self, serializer):
        # Add reporter if user is authenticated, otherwise save as anonymous
        reporter = self.request.user if self.request.user.is_authenticated else None
        
        serializer.save(
            reporter=reporter,
            ip_address=self.get_client_ip(self.request)
        )

        # Process facial recognition if photo is provided
        sighting = serializer.instance
        if sighting.photo and sighting.missing_person.recent_photo:
            self.process_facial_recognition(sighting)

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
        missing_person_id = request.query_params.get('missing_person_id')
        days = int(request.query_params.get('days', 30))

        queryset = Sighting.objects.filter(timestamp__gte=timezone.now() - timezone.timedelta(days=days))
        if missing_person_id:
            queryset = queryset.filter(missing_person_id=missing_person_id)

        data = {
            'total_sightings': queryset.count(),
            'by_status': queryset.values('verification_status').annotate(count=models.Count('id')),
            'heatmap_data': [
                {'lat': float(s.latitude), 'lng': float(s.longitude), 'count': 1}
                for s in queryset.filter(latitude__isnull=False, longitude__isnull=False)
            ]
        }
        return Response(data)