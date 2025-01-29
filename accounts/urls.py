# accounts/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, AadhaarProfileViewSet

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'aadhaar-profiles', AadhaarProfileViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
