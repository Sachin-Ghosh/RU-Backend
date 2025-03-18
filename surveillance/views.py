from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from .models import SurveillanceFootage
from .serializers import SurveillanceFootageSerializer
from .tasks import process_surveillance_footage
from missing_persons.models import MissingPerson
from math import radians, sin, cos, sqrt, asin

# Create your views here.

class SurveillanceFootageViewSet(viewsets.ModelViewSet):
    queryset = SurveillanceFootage.objects.all()
    serializer_class = SurveillanceFootageSerializer

    def perform_create(self, serializer):
        footage = serializer.save(uploaded_by=self.request.user)
        # Process footage asynchronously
        process_surveillance_footage.delay(footage.id)

    @action(detail=False, methods=['POST'])
    def search_missing_person(self, request):
        """Search for a missing person in surveillance footage"""
        missing_person_id = request.data.get('missing_person_id')
        radius = float(request.data.get('radius', 5.0))  # km
        
        if not missing_person_id:
            return Response(
                {'error': 'Missing person ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            missing_person = MissingPerson.objects.get(id=missing_person_id)
            
            # Get nearby footage based on last known location
            nearby_footage = self.get_nearby_footage(
                missing_person.last_known_latitude,
                missing_person.last_known_longitude,
                radius
            )
            
            # Process each footage
            for footage in nearby_footage:
                if not footage.processed:
                    process_surveillance_footage.delay(
                        footage.id,
                        missing_person_id
                    )
            
            return Response({
                'message': f'Processing {len(nearby_footage)} footage files',
                'footage_count': len(nearby_footage),
                'radius_km': radius
            })
            
        except MissingPerson.DoesNotExist:
            return Response(
                {'error': 'Missing person not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    def get_nearby_footage(self, lat, lon, radius):
        """Get footage within radius using Haversine formula"""
        lat, lon = float(lat), float(lon)
        
        # Get all footage
        queryset = SurveillanceFootage.objects.all()
        
        nearby = []
        for footage in queryset:
            try:
                distance = self.calculate_distance(
                    lat, lon,
                    float(footage.latitude),
                    float(footage.longitude)
                )
                if distance <= radius:
                    footage.distance = distance
                    nearby.append(footage)
            except:
                continue
                
        return nearby

    def calculate_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two points using Haversine formula"""
        R = 6371  # Earth's radius in km

        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        return R * c
