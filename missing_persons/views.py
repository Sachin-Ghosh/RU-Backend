from django.shortcuts import render
from django.db.models import Q, F
import tempfile
import os
from datetime import datetime
import json
import random
from math import radians, cos, sin, asin, sqrt

# Create your views here.

from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from .models import MissingPerson, MissingPersonDocument
from .serializers import MissingPersonSerializer, MissingPersonDocumentSerializer
from blockchain.services import BlockchainService
from blockchain.models import Block
from .services import BiometricService, MissingPersonService
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.core.files.base import ContentFile
import base64
# from django.contrib.gis.geos import Point
# from django.contrib.gis.db.models.functions import Distance
import numpy as np
from accounts.models import FamilyMember, FamilyGroup

class MissingPersonViewSet(viewsets.ModelViewSet):
    queryset = MissingPerson.objects.all()
    serializer_class = MissingPersonSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['status', 'gender']
    search_fields = ['name', 'case_number', 'aadhaar_number']
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_queryset(self):
        queryset = MissingPerson.objects.all()
        if not self.request.user.is_staff:
            # Show missing persons reported by user or their family members
            family_groups = self.request.user.families.all()
            queryset = queryset.filter(
                Q(reporter=self.request.user) |
                Q(family_group__in=family_groups)
            )
        return queryset

    def get_serializer_class(self):
        if self.action in ['retrieve', 'detail_search']:
            return MissingPersonSerializer
        return MissingPersonSerializer

    def create(self, request, *args, **kwargs):
        try:
            print("Files in request:", request.FILES)  # Debug print
            
            # Create a new dict for data
            data = {}
            
            # Separate files and data
            for key, value in request.data.items():
                if not key.startswith('documents[') and not hasattr(value, 'read'):
                    data[key] = value

            # Generate case number
            case_number = f"MP{''.join(random.choices('0123456789ABCDEF', k=8))}"
            data['case_number'] = case_number

            # Handle JSON fields
            for field in ['physical_attributes', 'possible_locations']:
                if field in data and isinstance(data[field], str):
                    try:
                        data[field] = json.loads(data[field])
                    except json.JSONDecodeError:
                        pass

            # Create missing person first
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            missing_person = serializer.save(
                reporter=request.user,
                case_number=case_number
            )

            # Handle documents
            document_indices = set()
            for key in request.data.keys():
                if key.startswith('documents['):
                    idx = int(key.split('[')[1].split(']')[0])
                    document_indices.add(idx)

            print("Document indices found:", document_indices)  # Debug print

            for idx in document_indices:
                doc_type = request.data.get(f'documents[{idx}][document_type]')
                doc_desc = request.data.get(f'documents[{idx}][description]')
                # Check both possible file keys
                doc_file = (
                    request.FILES.get(f'documents[{idx}][file]') or 
                    request.FILES.get(f'documents[{idx}][document]')
                )

                print(f"Processing document {idx}:")  # Debug print
                print(f"Type: {doc_type}")
                print(f"Description: {doc_desc}")
                print(f"File: {doc_file}")

                if doc_type and doc_desc and doc_file:
                    try:
                        document = MissingPersonDocument.objects.create(
                            missing_person=missing_person,
                            document_type=doc_type,
                            description=doc_desc,
                            file=doc_file,
                            uploaded_by=request.user
                        )
                        print(f"Document created: {document.id}")  # Debug print
                    except Exception as e:
                        print(f"Error creating document: {str(e)}")  # Debug print

            # Handle recent photo
            if 'recent_photo' in request.FILES:
                missing_person.recent_photo = request.FILES['recent_photo']
                missing_person.save()

            # Handle additional photos if any
            if 'additional_photos' in request.FILES:
                # You might want to handle additional photos here

            # Refresh instance to get updated data
                missing_person.refresh_from_db()
            return Response(
                self.get_serializer(missing_person).data,
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['GET'])
    def search(self, request):
        """Search missing persons by various parameters"""
        query = request.query_params.get('query', '')
        status = request.query_params.get('status')
        area = request.query_params.get('area')

        queryset = self.get_queryset()

        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) |
                Q(case_number__icontains=query) |
                Q(aadhaar_number__icontains=query)
            )

        if status:
            queryset = queryset.filter(status=status)

        if area:
            queryset = queryset.filter(
                Q(last_seen_location__icontains=area)
            )

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def haversine_distance(self, lat1, lon1, lat2, lon2):
        """
        Calculate the great circle distance between two points 
        on the earth (specified in decimal degrees)
        """
        try:
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
        except Exception as e:
            print(f"Error calculating distance: {str(e)}")
            return float('inf')

    @action(detail=False, methods=['GET'])
    def nearby(self, request):
        """Find missing persons within a radius"""
        try:
            lat = float(request.query_params.get('latitude'))
            lon = float(request.query_params.get('longitude'))
            radius = float(request.query_params.get('radius', 2.0))  # km
        except (TypeError, ValueError):
            return Response(
                {'error': 'Invalid latitude, longitude, or radius'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get all missing persons with location data
        queryset = MissingPerson.objects.exclude(
            last_known_latitude__isnull=True
        ).exclude(
            last_known_longitude__isnull=True
        )

        # Calculate distances and filter
        nearby_persons = []
        for person in queryset:
            try:
                distance = self.haversine_distance(
                    lat, lon,
                    float(person.last_known_latitude),
                    float(person.last_known_longitude)
                )
                if distance <= radius:
                    person.distance = distance  # Store distance as float
                    nearby_persons.append(person)
            except Exception as e:
                print(f"Error processing person {person.id}: {str(e)}")
                continue

        # Sort by distance
        nearby_persons.sort(key=lambda x: x.distance)
        
        serializer = self.get_serializer(nearby_persons, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='face-search')
    def face_search(self, request):
        """Search for missing persons using facial recognition"""
        if 'photo' not in request.FILES:
            return Response(
                {'error': 'Photo is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        search_photo = request.FILES['photo']
        matches = []

        # Save the uploaded photo temporarily
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            for chunk in search_photo.chunks():
                temp_file.write(chunk)
            temp_path = temp_file.name

        try:
            # Get all missing persons with photos
            persons = MissingPerson.objects.exclude(recent_photo='')

            for person in persons:
                try:
                    result = DeepFace.verify(
                        temp_path,
                        person.recent_photo.path,
                        model_name='VGG-Face'
                    )
                    
                    if result['verified']:
                        matches.append({
                            'person_id': person.id,
                            'name': person.name,
                            'case_number': person.case_number,
                            'confidence': result['distance']
                        })
                except Exception as e:
                    print(f"Error processing {person.id}: {str(e)}")

        finally:
            # Clean up the temporary file
            os.unlink(temp_path)

        return Response({'matches': matches})

    @action(detail=True, methods=['PATCH'])
    def update_status(self, request, pk=None):
        """Update the status of a missing person case"""
        instance = self.get_object()
        status = request.data.get('status')
        
        if status not in dict(MissingPerson.STATUS_CHOICES):
            return Response(
                {'error': 'Invalid status'},
                status=status.HTTP_400_BAD_REQUEST
            )

        instance.status = status
        instance.save()
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=True, methods=['POST'])
    def update_location(self, request, pk=None):
        """Update the last known location of a missing person"""
        instance = self.get_object()
        lat = request.data.get('latitude')
        lon = request.data.get('longitude')

        if not all([lat, lon]):
            return Response(
                {'error': 'Latitude and longitude are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        instance.last_known_latitude = lat
        instance.last_known_longitude = lon
        instance.save()

        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def match_biometrics(self, request):
        """Match uploaded biometric data against database"""
        photo = request.FILES.get('photo')
        fingerprint = request.FILES.get('fingerprint')
        
        if not (photo or fingerprint):
            return Response(
                {'error': 'No biometric data provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        biometric_service = BiometricService()
        matches = []
        
        if photo:
            person_id, confidence = biometric_service.match_face(photo.temporary_file_path())
            if confidence > 0.7:  # Threshold for matching
                matches.append({
                    'type': 'facial',
                    'person_id': person_id,
                    'confidence': confidence
                })
        
        if fingerprint:
            person_id, confidence = biometric_service.match_fingerprint(
                fingerprint.temporary_file_path()
            )
            if confidence > 0.7:
                matches.append({
                    'type': 'fingerprint',
                    'person_id': person_id,
                    'confidence': confidence
                })
        
        return Response({'matches': matches})

    @action(detail=False, methods=['post'])
    def report_self(self, request):
        """Report self as missing"""
        try:
            # Create missing person record for self
            missing_person = MissingPerson.objects.create(
                name=request.user.get_full_name(),
                registered_user=request.user,
                is_registered_user=True,
                reporter=request.user,
                reporter_type='SELF',
                # Pre-fill other fields from user profile
                **self.get_user_details(request.user)
            )
            
            return Response(
                MissingPersonSerializer(missing_person).data,
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['post'])
    def report_family_member(self, request):
        """Report a family member as missing"""
        family_member_id = request.data.get('family_member_id')
        if not family_member_id:
            return Response(
                {'error': 'Family member ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        details = MissingPersonService.get_family_member_details(family_member_id)
        if not details:
            return Response(
                {'error': 'Family member not found'},
                status=status.HTTP_404_NOT_FOUND
            )
            
        # Create missing person record with pre-filled details
        missing_person = MissingPerson.objects.create(
            reporter=request.user,
            reporter_type='FAMILY',
            **details,
            **request.data
        )
        
        return Response(
            MissingPersonSerializer(missing_person).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=False, methods=['GET'], url_path='detail-search')
    def detail_search(self, request):
        """
        Search for a missing person with detailed information including family data.
        """
        # Get query parameters
        case_number = request.query_params.get('case_number')
        name = request.query_params.get('name')
        aadhaar = request.query_params.get('aadhaar')
        phone = request.query_params.get('phone')
        location = request.query_params.get('location')

        # Start with all persons
        queryset = MissingPerson.objects.all()

        # Build query based on provided parameters
        filters = Q()
        
        if case_number:
            filters |= Q(case_number__iexact=case_number)
        
        if name:
            filters |= (Q(name__icontains=name) | 
                       Q(family_group__members__name__icontains=name))
        
        if aadhaar:
            filters |= (Q(aadhaar_number__iexact=aadhaar) | 
                       Q(family_group__members__aadhaar_number__iexact=aadhaar))
        
        if phone:
            filters |= (Q(emergency_contact_phone__icontains=phone) |
                       Q(secondary_contact_phone__icontains=phone) |
                       Q(family_group__members__contact_number__icontains=phone))
        
        if location:
            filters |= (Q(last_seen_location__icontains=location) |
                       Q(possible_locations__icontains=location))

        # If no search parameters provided
        if not any([case_number, name, aadhaar, phone, location]):
            return Response(
                {'error': 'Please provide at least one search parameter'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Apply filters
        queryset = queryset.filter(filters).distinct()

        # Optimize query
        queryset = queryset.select_related('family_group').prefetch_related(
            'documents',
            'family_group__members'
        )

        # Get results
        if not queryset.exists():
            return Response(
                {'message': 'No matching records found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Serialize the results
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

class MissingPersonDocumentViewSet(viewsets.ModelViewSet):
    queryset = MissingPersonDocument.objects.all()
    serializer_class = MissingPersonDocumentSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)