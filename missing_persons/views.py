from django.shortcuts import render
from django.db.models import Q
import tempfile
import os
from datetime import datetime
import json
import random

# Create your views here.

from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from .models import MissingPerson, MissingPersonDocument
from .serializers import MissingPersonSerializer, MissingPersonDocumentSerializer
from deepface import DeepFace
from blockchain.services import BlockchainService
from blockchain.models import Block
from .services import BiometricService, MissingPersonService
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

class MissingPersonViewSet(viewsets.ModelViewSet):
    queryset = MissingPerson.objects.all()
    serializer_class = MissingPersonSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['status', 'gender', 'city', 'state']
    search_fields = ['name', 'case_number', 'description']
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

    def create(self, request, *args, **kwargs):
        try:
            data = request.data.copy()

            # Handle JSON string fields
            json_fields = ['physical_attributes', 'last_seen_wearing', 'possible_locations']
            for field in json_fields:
                if field in data and isinstance(data[field], str):
                    try:
                        data[field] = json.loads(data[field])
                    except json.JSONDecodeError:
                        continue

            # Handle comma-separated strings
            list_fields = ['medical_conditions', 'medications', 'possible_locations']
            for field in list_fields:
                if field in data and isinstance(data[field], str):
                    if data[field].startswith('['):
                        try:
                            data[field] = json.loads(data[field])
                        except json.JSONDecodeError:
                            data[field] = [x.strip() for x in data[field].split(',')]
                    else:
                        data[field] = [x.strip() for x in data[field].split(',')]

            # Remove document fields from main data
            documents_data = []
            for key in list(data.keys()):
                if key.startswith('documents['):
                    idx = int(key.split('[')[1].split(']')[0])
                    while len(documents_data) <= idx:
                        documents_data.append({})
                    field = key.split('][')[1].split(']')[0]
                    documents_data[idx][field] = data[key]
                    del data[key]

            # Create missing person record
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            missing_person = serializer.save(
                reporter=request.user,
                case_number=self.generate_case_number()
            )

            # Create documents
            for doc_data in documents_data:
                if doc_data:
                    MissingPersonDocument.objects.create(
                        missing_person=missing_person,
                        document_type=doc_data.get('document_type'),
                        description=doc_data.get('description', ''),
                        uploaded_by=request.user
                    )

            # Refresh the instance to get updated data
            missing_person.refresh_from_db()
            
            return Response(
                MissingPersonSerializer(missing_person).data,
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            return Response(
                {'error': str(e), 'detail': getattr(e, 'detail', str(e))},
                status=status.HTTP_400_BAD_REQUEST
            )

    def generate_case_number(self):
        """Generate unique case number"""
        prefix = 'MP'
        random_suffix = ''.join(random.choices('0123456789ABCDEF', k=8))
        return f"{prefix}{random_suffix}"

    def perform_create(self, serializer):
        instance = serializer.save(reporter=self.request.user)
        biometric_service = BiometricService()
        
        # Process biometric data
        if instance.recent_photo:
            try:
                # Extract and analyze facial features
                facial_features = biometric_service.extract_facial_features(
                    instance.recent_photo.path
                )
                
                # Store in blockchain
                blockchain_data = {
                    'type': 'missing_person_registration',
                    'case_number': instance.case_number,
                    'facial_features': facial_features.tolist(),
                    'timestamp': instance.created_at.isoformat()
                }
                BlockchainService.add_block(blockchain_data, data_type='biometric')
                
            except Exception as e:
                print(f"Error processing biometric data: {str(e)}")

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        instance = self.get_object()
        status = request.data.get('status')
        if status in dict(MissingPerson.STATUS_CHOICES):
            instance.status = status
            instance.save()
            return Response({'status': 'updated'})
        return Response(
            {'error': 'Invalid status'},
            status=status.HTTP_400_BAD_REQUEST
        )

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

    @action(detail=False, methods=['post'])
    def search(self, request):
        """Search for missing persons using various criteria"""
        search_type = request.data.get('search_type')
        search_value = request.data.get('search_value')
        
        if search_type == 'name':
            results = MissingPersonService.search_by_name(search_value)
        elif search_type == 'aadhaar':
            results = MissingPersonService.search_by_aadhaar(search_value)
        elif search_type == 'photo':
            # Handle photo upload and matching
            photo = request.FILES.get('photo')
            if not photo:
                return Response(
                    {'error': 'Photo is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            # Save photo temporarily
            with tempfile.NamedTemporaryFile(delete=False) as temp_photo:
                for chunk in photo.chunks():
                    temp_photo.write(chunk)
                    
            try:
                matches = MissingPersonService.match_faces(temp_photo.name)
                results = [match['person'] for match in matches]
            finally:
                os.unlink(temp_photo.name)
        else:
            return Response(
                {'error': 'Invalid search type'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        return Response(
            MissingPersonSerializer(results, many=True).data
        )

    @action(detail=True, methods=['post'])
    def update_location(self, request, pk=None):
        """Update last known location of missing person"""
        missing_person = self.get_object()
        
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        timestamp = request.data.get('timestamp', datetime.now())
        
        if not all([latitude, longitude]):
            return Response(
                {'error': 'Latitude and longitude are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        MissingPersonService.update_location(
            missing_person,
            latitude,
            longitude,
            timestamp
        )
        
        return Response({'status': 'Location updated'})

class MissingPersonDocumentViewSet(viewsets.ModelViewSet):
    queryset = MissingPersonDocument.objects.all()
    serializer_class = MissingPersonDocumentSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)