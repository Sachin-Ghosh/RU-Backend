from warnings import filters
from django.shortcuts import render

# Create your views here.
# sightings/views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from .models import Sighting
from .serializers import SightingSerializer
from deepface import DeepFace
import numpy as np
from blockchain.services import BlockchainService

# import face_recognition

class SightingViewSet(viewsets.ModelViewSet):
    queryset = Sighting.objects.all()
    serializer_class = SightingSerializer
    permission_classes = [IsAuthenticated]
    # filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['verification_status', 'confidence_level']
    search_fields = ['location', 'description']

    def perform_create(self, serializer):
        # Process facial recognition if photo is provided
        photo = self.request.FILES.get('photo')
        missing_person = serializer.validated_data['missing_person']

        confidence = 0
        if photo and missing_person.recent_photo:
            try:
                # Use DeepFace for face verification
                result = DeepFace.verify(
                    img1_path=photo.temporary_file_path(),
                    img2_path=missing_person.recent_photo.path,
                    model_name='VGG-Face',
                    enforce_detection=False
                )
                
                confidence = result.get('distance', 0)
                verified = result.get('verified', False)
                
                # Add to blockchain
                blockchain_data = {
                    'type': 'sighting',
                    'missing_person_id': missing_person.id,
                    'location': serializer.validated_data.get('location'),
                    'timestamp': serializer.validated_data.get('timestamp').isoformat(),
                    'confidence': confidence,
                    'verified': verified
                }
                BlockchainService.add_block(blockchain_data)
                
                instance = serializer.save(
                    reporter=self.request.user,
                    facial_match_confidence=confidence
                )
            except Exception as e:
                instance = serializer.save(reporter=self.request.user)
        else:
            instance = serializer.save(reporter=self.request.user)

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        instance = self.get_object()
        status = request.data.get('verification_status')
        notes = request.data.get('verification_notes', '')

        if status in dict(Sighting.VERIFICATION_STATUS):
            instance.verification_status = status
            instance.verification_notes = notes
            instance.verified_by = request.user
            instance.save()
            return Response({'status': 'verified'})
        return Response(
            {'error': 'Invalid status'},
            status=status.HTTP_400_BAD_REQUEST
        )