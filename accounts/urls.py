# accounts/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, AadhaarProfileViewSet, FamilyViewSet
from . import views

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'aadhaar-profiles', AadhaarProfileViewSet)
router.register(r'families', FamilyViewSet, basename='family')

urlpatterns = [
    path('', include(router.urls)),
    path('login/', views.login_user, name='login'),
]
