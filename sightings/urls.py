# sightings/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SightingViewSet

router = DefaultRouter()
router.register(r'sightings', SightingViewSet)

urlpatterns = [
    path('', include(router.urls)),
]