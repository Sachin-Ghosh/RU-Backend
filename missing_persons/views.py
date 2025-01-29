from django.shortcuts import render

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
from .services import BiometricService

class MissingPersonViewSet(viewsets.ModelViewSet):
    queryset = MissingPerson.objects.all()
    serializer_class = MissingPersonSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['status', 'gender', 'city', 'state']
    search_fields = ['name', 'case_number', 'description']

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

class MissingPersonDocumentViewSet(viewsets.ModelViewSet):
    queryset = MissingPersonDocument.objects.all()
    serializer_class = MissingPersonDocumentSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)