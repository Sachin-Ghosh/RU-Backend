from django.shortcuts import render


from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import AuthenticationLog, BiometricAuth, OTPVerification
from .serializers import (
    AuthenticationLogSerializer,
    BiometricAuthSerializer,
    OTPVerificationSerializer
)

class AuthenticationLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuthenticationLog.objects.all()
    serializer_class = AuthenticationLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return AuthenticationLog.objects.filter(user=self.request.user)

class BiometricAuthViewSet(viewsets.ModelViewSet):
    queryset = BiometricAuth.objects.all()
    serializer_class = BiometricAuthSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return BiometricAuth.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        # Implement biometric verification logic here
        return Response({'status': 'verified'})

class OTPVerificationViewSet(viewsets.ModelViewSet):
    queryset = OTPVerification.objects.all()
    serializer_class = OTPVerificationSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'])
    def generate(self, request):
        # Implement OTP generation logic here
        return Response({'status': 'OTP generated'})

    @action(detail=False, methods=['post'])
    def verify(self, request):
        # Implement OTP verification logic here
        return Response({'status': 'verified'})