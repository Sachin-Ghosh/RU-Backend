# missing_persons/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MissingPersonViewSet, MissingPersonDocumentViewSet

router = DefaultRouter()
router.register(r'missing-persons', MissingPersonViewSet)
router.register(r'documents', MissingPersonDocumentViewSet)

urlpatterns = [
    path('', include(router.urls)),
]