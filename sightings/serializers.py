# sightings/serializers.py

from rest_framework import serializers
from .models import Sighting
from missing_persons.models import MissingPerson
from missing_persons.serializers import MissingPersonSerializer

class SightingSerializer(serializers.ModelSerializer):
    reporter_name = serializers.CharField(required=False, allow_blank=True)
    reporter_contact = serializers.CharField(required=False, allow_blank=True)
    missing_person_name = serializers.SerializerMethodField()
    verified_by_name = serializers.SerializerMethodField()
    missing_person = MissingPersonSerializer(read_only=True)
    
    class Meta:
        model = Sighting
        fields = [
            'id', 'missing_person', 'missing_person_name', 
            'reporter', 'reporter_name', 'reporter_contact', 'timestamp',
            'location', 'latitude', 'longitude',
            'location_details', 'direction_headed',
            'description', 'wearing', 'accompanied_by',
            'photo', 'additional_photos', 'video',
            'verification_status', 'verified_by', 'verified_by_name',
            'verification_notes', 'confidence_level',
            'facial_match_confidence', 'ml_analysis_results',
            'created_at', 'updated_at', 'ip_address',
            'device_info', 'is_notified'
        ]
        read_only_fields = [
            'reporter', 'facial_match_confidence',
            'created_at', 'updated_at', 'ip_address',
            'device_info', 'verified_by', 'verified_by_name',
            'missing_person', 'reporter_name', 'is_notified'
        ]

    def get_reporter_name(self, obj):
        if obj.reporter:
            return obj.reporter.get_full_name()
        return obj.reporter_name or "Anonymous"

    def get_missing_person_name(self, obj):
        return obj.missing_person.name if obj.missing_person else None

    def get_verified_by_name(self, obj):
        return obj.verified_by.get_full_name() if obj.verified_by else None

    def create(self, validated_data):
        # Add IP address and device info from request
        request = self.context.get('request')
        if request and not request.user.is_authenticated:
            # For anonymous users, ensure we have some contact information
            if not validated_data.get('reporter_name') and not validated_data.get('reporter_contact'):
                raise serializers.ValidationError({
                    'reporter_contact': 'Please provide either a name or contact information for anonymous reports'
                })
        
        # Add IP address and device info
        if request:
            validated_data['ip_address'] = self.get_client_ip(request)
            validated_data['device_info'] = self.get_device_info(request)
            if request.user.is_authenticated:
                validated_data['reporter'] = request.user

        return super().create(validated_data)

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')

    def get_device_info(self, request):
        return {
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'platform': request.META.get('HTTP_SEC_CH_UA_PLATFORM', ''),
            'mobile': request.META.get('HTTP_SEC_CH_UA_MOBILE', '')
        }