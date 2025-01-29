# authentication/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AuthenticationLogViewSet,
    BiometricAuthViewSet,
    OTPVerificationViewSet
)

router = DefaultRouter()
router.register(r'auth-logs', AuthenticationLogViewSet)
router.register(r'biometric-auth', BiometricAuthViewSet)
router.register(r'otp', OTPVerificationViewSet)

urlpatterns = [
    path('', include(router.urls)),
]