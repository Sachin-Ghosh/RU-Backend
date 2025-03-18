from django.shortcuts import render

# Create your views here.
# accounts/views.py

from rest_framework import viewsets, status, generics
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import get_user_model, authenticate
from .models import User, AadhaarProfile, FamilyGroup, FamilyMember
from .serializers import (
    UserSerializer, UserDetailSerializer, AadhaarProfileSerializer,
    FamilyGroupSerializer, FamilyMemberSerializer
)
from .services import RegistrationService, OTPService
from rest_framework_simplejwt.tokens import RefreshToken

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    
    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.action in ['register_with_aadhaar', 'create', 'send_otp', 'verify_otp']:
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
                aadhaar_profile = RegistrationService.process_registration(
                    user,
                    aadhaar_image,
                    profile_picture,
                    fingerprint
                )
                
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
                    'message': 'User registered successfully with biometric data'
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

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def verify_otp(self, request):
        phone_or_email = request.data.get('phone_or_email')
        otp = request.data.get('otp')
        if not (phone_or_email and otp):
            return Response({'error': 'Phone/email and OTP are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        otp_service = OTPService()
        user_data = otp_service.verify_otp(phone_or_email, otp)
        if user_data:
            user = User.objects.get(email=user_data['email']) if '@' in phone_or_email else User.objects.get(phone_number=phone_or_email)
            refresh = RefreshToken.for_user(user)
            return Response({
                'message': 'OTP verified successfully',
                'tokens': {'access': str(refresh.access_token), 'refresh': str(refresh)},
                'user': UserSerializer(user).data
            }, status=status.HTTP_200_OK)
        return Response({'error': 'Invalid OTP'}, status=status.HTTP_400_BAD_REQUEST)

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
            required_fields = ['organization_name', 'email', 'password', 'phone_number', 'role']
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
                'username': request.data.get('email'),  # Use email as username
                'email': request.data.get('email'),
                'password': request.data.get('password'),
                'phone_number': request.data.get('phone_number'),
                'role': role,
                'organization': request.data.get('organization_name'),
                'is_approved': False,  # Requires admin approval
                'is_verified': False,  # Requires email verification
            }

            # Handle verification documents
            verification_docs = request.FILES.getlist('verification_documents')
            if not verification_docs:
                return Response(
                    {'error': 'Verification documents are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            user_serializer = UserSerializer(data=user_data)
            if not user_serializer.is_valid():
                return Response(
                    user_serializer.errors,
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            user = user_serializer.save()

            # Send verification email
            otp_service = OTPService()
            otp_service.send_otp(user.email)

            return Response({
                'message': 'Organization registered successfully. Please verify your email and wait for admin approval.',
                'user': UserSerializer(user).data
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            if 'user' in locals():
                user.delete()
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
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
    """
    Login API that returns JWT tokens and user data
    """
    try:
        username = request.data.get('username')
        password = request.data.get('password')

        # Validate input
        if not username or not password:
            return Response(
                {'error': 'Please provide both username and password'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Authenticate user
        user = authenticate(username=username, password=password)

        if user is None:
            return Response(
                {'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not user.is_active:
            return Response(
                {'error': 'User account is disabled'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Generate tokens
        refresh = RefreshToken.for_user(user)
        
        # Get user data
        user_serializer = UserSerializer(user)

        # Return response with tokens and user data
        return Response({
            'message': 'Login successful',
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            },
            'user': user_serializer.data
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )