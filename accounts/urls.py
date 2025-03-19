# accounts/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, AadhaarProfileViewSet, FamilyViewSet, CollaborationViewSet
from . import views

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'aadhaar-profiles', AadhaarProfileViewSet)
router.register(r'families', FamilyViewSet, basename='family')
router.register(r'collaborations', CollaborationViewSet, basename='collaboration')

urlpatterns = [
    path('', include(router.urls)),
    path('login/', views.login_user, name='login'),
    path('approve-organization/', views.approve_organization, name='approve-organization'),
    path('organizations/', views.list_organizations, name='list_organizations'),
]
