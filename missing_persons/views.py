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
from .services import BiometricService, MissingPersonService,PosterService,AnalyticsService
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.core.files.base import ContentFile
import base64
from deepface import DeepFace
# from django.contrib.gis.geos import Point
# from django.contrib.gis.db.models.functions import Distance
import numpy as np
from accounts.models import FamilyMember, FamilyGroup
from accounts.models import User
# from rest_framework.parsers import MultiPartParser, FormParser
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import fitz  # PyMuPDF
import uuid
import cloudinary.uploader
import requests
from urllib.parse import quote

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
            
            # data['reporter'] = request.user.id
            
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
            
    @action(detail=True, methods=['post'])
    def generate_poster(self, request, pk=None):
        missing_person = self.get_object()
        poster_service = PosterService()
        poster_file = poster_service.generate_poster(missing_person)
        
        missing_person.poster_image.save(f'{missing_person.case_number}_poster.png', poster_file)
        missing_person.save()
        
        serializer = self.get_serializer(missing_person)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def share_poster(self, request, pk=None):
        missing_person = self.get_object()
        platform = request.data.get('platform')
        
        if not missing_person.poster_image:
            return Response({'error': 'Poster not generated yet'}, status=status.HTTP_400_BAD_REQUEST)
        
        poster_url = missing_person.poster_image.url
        if platform == 'instagram':
            # Simplified Instagram posting (assuming credentials are configured)
            upload_result = cloudinary.uploader.upload(missing_person.poster_image.path)
            return Response({'url': upload_result['secure_url'], 'message': 'Posted to Instagram'})
        elif platform == 'whatsapp':
            return Response({'url': poster_url, 'message': 'Poster URL ready for WhatsApp'})
        return Response({'error': 'Unsupported platform'}, status=status.HTTP_400_BAD_REQUEST)
    
    
    @action(detail=False, methods=['get'])
    def analytics(self, request):
        analytics_service = AnalyticsService()
        data = {
            'total_cases': analytics_service.get_total_cases(),
            'cases_by_region': analytics_service.get_cases_by_region(),
            'resolution_rate': analytics_service.get_resolution_rate(),
            'heatmap_data': analytics_service.get_heatmap_data()
        }
        return Response(data)

    @action(detail=True, methods=['post'])
    def assign_collaborator(self, request, pk=None):
        missing_person = self.get_object()
        collaborator_id = request.data.get('collaborator_id')
        collaborator_type = request.data.get('type')  # 'officer' or 'ngo'
        
        collaborator = User.objects.get(id=collaborator_id)
        if collaborator_type == 'officer':
            missing_person.assigned_officer = collaborator
        elif collaborator_type == 'ngo':
            missing_person.assigned_ngo = collaborator
        else:
            return Response({'error': 'Invalid collaborator type'}, status=status.HTTP_400_BAD_REQUEST)
        
        missing_person.save()
        return Response(self.get_serializer(missing_person).data)

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

    @action(detail=False, methods=['POST'], url_path='aadhaar-search')
    def search_by_aadhaar(self, request):
        """
        Search for missing persons by Aadhaar number or Aadhaar card photo
        """
        aadhaar_number = request.data.get('aadhaar_number')
        aadhaar_photo = request.FILES.get('aadhaar_photo')

        if not aadhaar_number and not aadhaar_photo:
            return Response(
                {'error': 'Please provide either Aadhaar number or Aadhaar card photo'},
                status=status.HTTP_400_BAD_REQUEST
            )

        matches = []

        # Search by Aadhaar number
        if aadhaar_number:
            persons = MissingPerson.objects.filter(
                aadhaar_number=aadhaar_number
            )
            if persons.exists():
                serializer = self.get_serializer(persons, many=True)
                return Response(serializer.data)

        # Search by Aadhaar photo
        if aadhaar_photo:
            # Save uploaded photo temporarily
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                for chunk in aadhaar_photo.chunks():
                    temp_file.write(chunk)
                temp_path = temp_file.name

            try:
                # Get all Aadhaar card documents
                aadhaar_docs = MissingPersonDocument.objects.filter(
                    document_type='ID_PROOF',
                    description__icontains='Aadhaar'
                )

                # Compare with each Aadhaar document
                for doc in aadhaar_docs:
                    try:
                        result = DeepFace.verify(
                            temp_path,
                            doc.file.path,
                            model_name='VGG-Face',
                            distance_metric='cosine'
                        )

                        if result.get('verified', False):
                            missing_person = doc.missing_person
                            match_data = {
                                'person': missing_person,
                                'confidence': result.get('distance', 0)
                            }
                            matches.append(match_data)
                    except Exception as e:
                        print(f"Error processing document {doc.id}: {str(e)}")
                        continue

            finally:
                # Clean up temporary file
                os.unlink(temp_path)

            # Sort matches by confidence
            matches.sort(key=lambda x: x['confidence'], reverse=True)

            # Return results
            if matches:
                persons = [match['person'] for match in matches]
                serializer = self.get_serializer(persons, many=True)
                return Response({
                    'matches': serializer.data,
                    'match_confidences': [match['confidence'] for match in matches]
                })

        return Response(
            {'message': 'No matching records found'},
            status=status.HTTP_404_NOT_FOUND
        )

    @action(detail=False, methods=['POST'], url_path='convert-and-post')
    def convert_pdf_and_post(self, request):
        """
        Convert PDF to PNG, save both files, upload to Cloudinary, and post to Instagram
        """
        if 'pdf_file' not in request.FILES:
            return Response(
                {'error': 'Please provide a PDF file'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Instagram API configuration
        INSTAGRAM_ACCOUNT_ID = "17841468077947131"
        ACCESS_TOKEN = "EAAX4kmSL4uMBO77bTujUCmsLN4WsZBGwpkehN51bqbYUXb2RDZBBc2iU9hnxy5ptr8Y7QqWpLYXWatRqR4N29Wd321FC0hwV3edugzJb0uvOFmjUtxAbm5bOi9GgHtE8FaHR1mXMiqnrkh9bEhYNwShSlTLNhF9npqb429hdtegc2m1CBb9fJo"

        try:
            # pdf_file = request.FILES['pdf_file']
            # case_number = request.data.get('case_number')
            # person_name = request.data.get('person_name', '')

            # # Save PDF file
            # pdf_path = f'posters/{case_number}_poster.pdf'
            # with default_storage.open(pdf_path, 'wb+') as destination:
            #     for chunk in pdf_file.chunks():
            #         destination.write(chunk)
            # Step 1: Convert PDF and upload to Cloudinary
            cloudinary_url = self.convert_to_cloudinary(request.FILES['pdf_file'])
            if not cloudinary_url:
                return Response(
                    {'error': 'Failed to convert and upload PDF'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Step 2: Create Instagram media container
            creation_id = self.create_instagram_container(
                cloudinary_url,
                INSTAGRAM_ACCOUNT_ID,
                ACCESS_TOKEN,
                request.data.get('person_name', '')  # Get person's name from request
            )
            if not creation_id:
                return Response(
                    {'error': 'Failed to create Instagram media container'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Step 3: Publish to Instagram
            published = self.publish_to_instagram(
                creation_id,
                INSTAGRAM_ACCOUNT_ID,
                ACCESS_TOKEN
            )
            if not published:
                return Response(
                    {'error': 'Failed to publish to Instagram'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            return Response({
                'message': 'Successfully converted and posted to Instagram',
                'cloudinary_url': cloudinary_url,
                'instagram_post_id': published.get('id')
            })

        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return Response(
                {'error': f'Process failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def convert_to_cloudinary(self, pdf_file):
        """Convert PDF to PNG and upload to Cloudinary"""
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                # Save PDF temporarily
                temp_pdf_path = os.path.join(temp_dir, 'temp.pdf')
                with open(temp_pdf_path, 'wb') as f:
                    for chunk in pdf_file.chunks():
                        f.write(chunk)

                # Convert first page to PNG
                pdf_document = fitz.open(temp_pdf_path)
                page = pdf_document[0]
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                
                # Save PNG temporarily
                temp_png_path = os.path.join(temp_dir, 'temp.png')
                pix.save(temp_png_path)
                
                # Upload to Cloudinary
                upload_result = cloudinary.uploader.upload(
                    temp_png_path,
                    folder='pdf_conversions',
                    public_id=f'pdf_convert_{uuid.uuid4().hex}_1'
                )
                
                pdf_document.close()
                return upload_result['secure_url']

        except Exception as e:
            print(f"Conversion error: {str(e)}")
            return None

    def create_instagram_container(self, image_url, account_id, access_token, person_name):
        """Create Instagram media container"""
        try:
            caption = (
                f"Please help us find the above person. If you have any information, "
                f"please contact on the given info or local authorities immediately.\n"
                f"📢 Share & spread the word! Every share helps bring them home. "
                f"🙏💙 #MissingPerson #HelpFind{person_name} #SpreadTheWord"
            )

            url = (
                f"https://graph.facebook.com/v20.0/{account_id}/media"
                f"?image_url={quote(image_url)}"
                f"&caption={quote(caption)}"
                f"&access_token={access_token}"
                f"&media_type=IMAGE"
            )

            response = requests.post(url)
            response.raise_for_status()
            data = response.json()
            return data.get('id')

        except Exception as e:
            print(f"Container creation error: {str(e)}")
            return None

    def publish_to_instagram(self, creation_id, account_id, access_token):
        """Publish to Instagram"""
        try:
            url = (
                f"https://graph.facebook.com/v20.0/{account_id}/media_publish"
                f"?creation_id={creation_id}"
                f"&access_token={access_token}"
            )

            response = requests.post(url)
            response.raise_for_status()
            return response.json()

        except Exception as e:
            print(f"Publishing error: {str(e)}")
            return None

class MissingPersonDocumentViewSet(viewsets.ModelViewSet):
    queryset = MissingPersonDocument.objects.all()
    serializer_class = MissingPersonDocumentSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)