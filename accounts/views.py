from django.shortcuts import render
from django.core.mail import send_mail

# Create your views here.
# accounts/views.py

from rest_framework import viewsets, status, generics
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import get_user_model, authenticate
from .models import User, AadhaarProfile, FamilyGroup, FamilyMember,Collaboration,CollaborationMessage
from .serializers import (
    UserSerializer, UserDetailSerializer, AadhaarProfileSerializer,
    FamilyGroupSerializer, FamilyMemberSerializer,CollaborationMessageSerializer,CollaborationSerializer
)
from .services import RegistrationService, OTPService, UserAnalyticsService
from rest_framework_simplejwt.tokens import RefreshToken
import logging
from django.conf import settings

from accounts import serializers

from accounts import models


logger = logging.getLogger(__name__)
User = get_user_model()

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    
    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.action in ['register_with_aadhaar', 'create', 'send_otp', 'verify_otp', 'register_organization']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def register_with_aadhaar(self, request):
        """Register user with Aadhaar and biometric data"""
        try:
            # First create the user
            user_data = {
                'username': request.data.get('username'),
                'password': request.data.get('password'),  # Make sure password is included
                'email': request.data.get('email'),
                'first_name': request.data.get('first_name'),
                'middle_name': request.data.get('middle_name'),
                'profile_picture': request.data.get('profile_picture'),
                'last_name': request.data.get('last_name'),
                'phone_number': request.data.get('phone_number'),
                'role': request.data.get('role', 'CITIZEN'),
                'address': request.data.get('address'),
                'city': request.data.get('city'),
                'state': request.data.get('state'),
                'pincode': request.data.get('pincode'),
                'latitude': request.data.get('latitude'),
                'longitude': request.data.get('longitude'),
                'dob': request.data.get('dob'),
                'gender': request.data.get('gender'),
                'is_approved': True  # Auto-approve regular citizens
            }
            

            # Validate password
            if not user_data.get('password'):
                return Response(
                    {'error': 'Password is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            user_serializer = UserSerializer(data=user_data)
            if not user_serializer.is_valid():
                return Response(
                    user_serializer.errors,
                    status=status.HTTP_400_BAD_REQUEST
                )
            user = user_serializer.save()
            refresh = RefreshToken.for_user(user)
            # Process biometric registration
            aadhaar_image = request.FILES.get('aadhaar_image')
            profile_picture = request.FILES.get('profile_picture')
            fingerprint = request.FILES.get('fingerprint')
            
            # Validate required files
            if not aadhaar_image:
                return Response(
                    {'error': 'Aadhaar image is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if not profile_picture:
                return Response(
                    {'error': 'profile_picture is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate file types
            allowed_types = ['image/jpeg', 'image/png']
            if aadhaar_image.content_type not in allowed_types:
                return Response(
                    {'error': 'Aadhaar image must be JPEG or PNG'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if profile_picture.content_type not in allowed_types:
                return Response(
                    {'error': 'profile_picture must be JPEG or PNG'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if fingerprint and fingerprint.content_type not in allowed_types:
                return Response(
                    {'error': 'Fingerprint must be JPEG or PNG'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                # Send verification email
                otp_service = OTPService()
                if not otp_service.send_otp(user.email):
                    user.delete()
                    return Response(
                        {'error': 'Failed to send verification email'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

                # Process biometric registration
                aadhaar_profile = RegistrationService.process_registration(
                    user,
                    aadhaar_image,
                    profile_picture,
                    fingerprint
                )
                user.is_approved = True
                user.save()
                # Generate tokens
                refresh = RefreshToken.for_user(user)
                tokens = {
                    'access': str(refresh.access_token),
                    'refresh': str(refresh)
                }
                
                response_data = {
                    'user': UserSerializer(user).data,
                    'tokens': tokens,
                    'aadhaar_profile': AadhaarProfileSerializer(aadhaar_profile).data,
                    'message': 'User registered successfully. Please verify your email with the OTP sent.'
                }
                
            except Exception as e:
                user.delete()  # Clean up if biometric registration fails
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            # Clean up if registration fails
            if 'user' in locals():
                user.delete()
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'])
    def me(self, request):
        serializer = UserDetailSerializer(request.user)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def send_otp(self, request):
        phone_or_email = request.data.get('phone_or_email')
        if not phone_or_email:
            return Response({'error': 'Phone or email is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        otp_service = OTPService()
        success = otp_service.send_otp(phone_or_email)
        if success:
            return Response({'message': 'OTP sent successfully'}, status=status.HTTP_200_OK)
        return Response({'error': 'Failed to send OTP'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['POST'], permission_classes=[AllowAny])
    def verify_otp(self, request):
        """Verify OTP for email/phone verification"""
        try:
            # Get email/phone and OTP from request data
            email_or_phone = request.data.get('email_or_phone') or request.data.get('email')  # Accept both field names
            otp = request.data.get('otp')
            
            logger.info(f"Verifying OTP request for {email_or_phone}")

            if not email_or_phone or not otp:
                return Response({
                    'error': 'Email/Phone and OTP are required',
                    'received_data': {
                        'email_or_phone': email_or_phone,
                        'otp': otp
                    }
                }, status=status.HTTP_400_BAD_REQUEST)

            otp_service = OTPService()
            result = otp_service.verify_otp(email_or_phone, otp)
            
            if result:
                return Response({
                    'message': 'Email verified successfully',
                    'is_verified': True
                }, status=status.HTTP_200_OK)
            
            return Response({
                'error': 'Invalid or expired OTP'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            logger.error(f"Error in verify_otp view: {str(e)}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return UserDetailSerializer
        return UserSerializer
    
    @action(detail=False, methods=['patch'])
    def update_settings(self, request):
        user = request.user
        serializer = UserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def verify_aadhaar(self, request, pk=None):
        user = self.get_object()
        # Implement Aadhaar verification logic here
        return Response({'status': 'verification initiated'})

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def register_organization(self, request):
        """Register NGO or Law Enforcement organization"""
        try:
            # Basic validation
            required_fields = [
                'organization_name', 'email', 'password', 'phone_number', 'role',
                'first_name', 'last_name'
            ]
            for field in required_fields:
                if not request.data.get(field):
                    return Response(
                        {'error': f'{field} is required'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            role = request.data.get('role')
            if role not in ['NGO', 'LAW_ENFORCEMENT']:
                return Response(
                    {'error': 'Invalid role. Must be NGO or LAW_ENFORCEMENT'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create user data
            user_data = {
                'username': request.data.get('email'),
                'email': request.data.get('email'),
                'password': request.data.get('password'),
                'phone_number': request.data.get('phone_number'),
                'role': role,
                'organization': request.data.get('organization_name'),
                'first_name': request.data.get('first_name'),
                'last_name': request.data.get('last_name'),
                'middle_name': request.data.get('middle_name', ''),
                'is_approved': False,
                'is_verified': False,
                'organization_latitude': request.data.get('organization_latitude'),
                'organization_longitude': request.data.get('organization_longitude'),
                'organization_location': request.data.get('organization_location'),
            }

            user_serializer = UserSerializer(data=user_data, context={'request': request})
            if not user_serializer.is_valid():
                return Response(
                    user_serializer.errors,
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            user = user_serializer.save()

            # Handle verification documents
            verification_docs = request.FILES.getlist('verification_documents')
            if verification_docs:
                from accounts.models import VerificationDocument
                for doc in verification_docs:
                    VerificationDocument.objects.create(
                        user=user,
                        document=doc,
                        document_type='ORGANIZATION_VERIFICATION'
                    )

            # Send verification email
            otp_service = OTPService()
            if not otp_service.send_otp(user.email):
                user.delete()
                return Response(
                    {'error': 'Failed to send verification email'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Get updated user data with verification documents
            updated_serializer = UserSerializer(user, context={'request': request})
            return Response({
                'message': 'Organization registered successfully. Please verify your email with the OTP sent.',
                'user': updated_serializer.data
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            if 'user' in locals():
                user.delete()
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['GET'])
    def analytics(self, request):
        """Get user analytics"""
        try:
            if not request.user.is_authenticated:
                return Response(
                    {'error': 'Authentication required'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            if request.user.role != 'ADMIN':
                return Response(
                    {'error': 'Only admins can access analytics'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            logger.info(f"Generating analytics for admin user: {request.user.username}")
            
            analytics_service = UserAnalyticsService()
            statistics = analytics_service.get_user_statistics()
            
            if statistics is not None:
                logger.info("Successfully generated analytics")
                return Response(statistics, status=status.HTTP_200_OK)
            
            logger.error("Failed to generate statistics - returned None")
            return Response(
                {'error': 'Failed to generate statistics. Please check server logs.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
        except Exception as e:
            logger.error(f"Error in analytics view: {str(e)}")
            logger.exception("Full traceback:")
            return Response(
                {'error': f'Error generating analytics: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class AadhaarProfileViewSet(viewsets.ModelViewSet):
    queryset = AadhaarProfile.objects.all()
    serializer_class = AadhaarProfileSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class FamilyViewSet(viewsets.ModelViewSet):
    serializer_class = FamilyGroupSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return FamilyGroup.objects.filter(members=self.request.user)

    def perform_create(self, serializer):
        family = serializer.save(
            created_by=self.request.user,
            passkey=FamilyGroup.generate_passkey()
        )
        # Add creator as admin
        FamilyMember.objects.create(
            user=self.request.user,
            family=family,
            role='ADMIN',
            relationship='Creator'
        )

    @action(detail=False, methods=['post'])
    def join(self, request):
        """Join a family using passkey"""
        passkey = request.data.get('passkey')
        relationship = request.data.get('relationship')

        if not passkey or not relationship:
            return Response(
                {'error': 'Passkey and relationship are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            family = FamilyGroup.objects.get(passkey=passkey)
            
            # Check if user is already a member
            if FamilyMember.objects.filter(user=request.user, family=family).exists():
                return Response(
                    {'error': 'Already a member of this family'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Add user as member
            member = FamilyMember.objects.create(
                user=request.user,
                family=family,
                role='MEMBER',
                relationship=relationship
            )

            return Response(
                FamilyMemberSerializer(member).data,
                status=status.HTTP_201_CREATED
            )

        except FamilyGroup.DoesNotExist:
            return Response(
                {'error': 'Invalid passkey'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['get'])
    def members(self, request, pk=None):
        """Get all members of a family"""
        family = self.get_object()
        members = FamilyMember.objects.filter(family=family)
        serializer = FamilyMemberSerializer(members, many=True)
        return Response(serializer.data)

@api_view(['POST'])
@permission_classes([AllowAny])
def login_user(request):
    """Login API that accepts both username and email"""
    try:
        username_or_email = request.data.get('username')
        password = request.data.get('password')

        if not username_or_email or not password:
            return Response(
                {'error': 'Please provide both username/email and password'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Try to get user by username or email
        try:
            if '@' in username_or_email:
                user = User.objects.get(email=username_or_email)
            else:
                user = User.objects.get(username=username_or_email)
        except User.DoesNotExist:
            return Response(
                {'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Authenticate user
        user = authenticate(username=user.username, password=password)

        if not user:
            return Response(
                {'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not user.is_active:
            return Response(
                {'error': 'User account is disabled'},
                status=status.HTTP_403_FORBIDDEN
            )

        if not user.is_verified:
            return Response(
                {'error': 'Please verify your email first'},
                status=status.HTTP_403_FORBIDDEN
            )

        if not user.is_approved and user.role in ['NGO', 'LAW_ENFORCEMENT']:
            return Response(
                {'error': 'Account approval pending'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Generate tokens
        refresh = RefreshToken.for_user(user)

        return Response({
            'message': 'Login successful',
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            },
            'user': UserDetailSerializer(user).data
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        
# New admin views
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def approve_organization(request):
    """Admin endpoint to approve an organization"""
    try:
        # Check if user is admin
        if not request.user.is_staff and request.user.role != 'ADMIN':
            return Response(
                {'error': 'Only admins can approve organizations'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get user_id from request data
        user_id = request.data.get('user_id')
        if not user_id:
            return Response(
                {'error': 'User ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Convert user_id to integer if it's a string
            user_id = int(user_id)
            user = User.objects.get(id=user_id)
            
            # Verify this is an organization account
            if user.role not in ['NGO', 'LAW_ENFORCEMENT']:
                return Response(
                    {'error': 'User is not an organization'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Update approval status
            user.is_approved = True
            user.save()

            # Send approval email
            try:
                subject = 'Organization Account Approved'
                message = f"""
                Dear {user.get_full_name()},

                Your organization account ({user.organization}) has been approved. 
                You can now log in to the system and access all features.

                Best regards,
                Admin Team
                """
                
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    fail_silently=True,
                )
            except Exception as e:
                # Log email error but don't fail the request
                logger.error(f"Failed to send approval email to {user.email}: {str(e)}")

            return Response({
                'message': 'Organization approved successfully',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'organization': user.organization,
                    'role': user.role,
                    'is_approved': user.is_approved
                }
            }, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response(
                {'error': f'User with ID {user_id} not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except ValueError:
            return Response(
                {'error': 'Invalid user ID format'},
                status=status.HTTP_400_BAD_REQUEST
            )

    except Exception as e:
        logger.error(f"Error in approve_organization: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_organizations(request):
    """List all organizations (NGOs and Law Enforcement)"""
    try:
        organizations = User.objects.filter(role__in=['NGO', 'LAW_ENFORCEMENT'])
        serializer = UserSerializer(organizations, many=True, context={'request': request})
        
        return Response({
            'count': organizations.count(),
            'results': serializer.data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        
class CollaborationViewSet(viewsets.ModelViewSet):
    serializer_class = CollaborationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.role not in ['NGO', 'LAW_ENFORCEMENT']:
            return Collaboration.objects.none()
        return Collaboration.objects.filter(
            models.Q(initiator=user) | models.Q(collaborator=user)
        )
    
    def perform_create(self, serializer):
        # Validate that initiator is either NGO or Police
        user = self.request.user
        if user.role not in ['NGO', 'LAW_ENFORCEMENT']:
            raise serializers.ValidationError(
                "Only NGOs and Law Enforcement can initiate collaborations"
            )
        
        collaborator_id = self.request.data.get('collaborator')
        try:
            collaborator = User.objects.get(id=collaborator_id)
            if collaborator.role not in ['NGO', 'LAW_ENFORCEMENT']:
                raise serializers.ValidationError(
                    "Can only collaborate with NGOs or Law Enforcement"
                )
            if collaborator == user:
                raise serializers.ValidationError(
                    "Cannot collaborate with yourself"
                )
        except User.DoesNotExist:
            raise serializers.ValidationError("Collaborator not found")
            
        serializer.save(initiator=user, collaborator=collaborator)
    
    @action(detail=True, methods=['post'])
    def send_message(self, request, pk=None):
        collaboration = self.get_object()
        if request.user not in [collaboration.initiator, collaboration.collaborator]:
            return Response(
                {'error': 'Not authorized'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        message_data = {
            'collaboration': collaboration.id,
            'sender': request.user.id,
            'message': request.data.get('message'),
            'file_attachment': request.FILES.get('file_attachment')
        }
        
        serializer = CollaborationMessageSerializer(data=message_data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['patch'])
    def update_status(self, request, pk=None):
        collaboration = self.get_object()
        if request.user not in [collaboration.initiator, collaboration.collaborator]:
            return Response(
                {'error': 'Not authorized'},
                status=status.HTTP_403_FORBIDDEN
            )
            
        status = request.data.get('status')
        if status not in dict(Collaboration.STATUS_CHOICES):
            return Response(
                {'error': 'Invalid status'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        collaboration.status = status
        collaboration.save()
        
        # Send notification to other party
        other_party = (collaboration.initiator 
                      if request.user == collaboration.collaborator 
                      else collaboration.collaborator)
        
        if other_party.notification_preferences.get('email', False):
            send_mail(
                subject=f'Collaboration Status Update - Case #{collaboration.id}',
                message=f'The collaboration status has been updated to {status}.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[other_party.email],
                fail_silently=True
            )
            
        return Response(
            CollaborationSerializer(collaboration).data,
            status=status.HTTP_200_OK
        )