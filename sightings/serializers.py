# sightings/serializers.py

from rest_framework import serializers
from .models import Sighting

class SightingSerializer(serializers.ModelSerializer):
    reporter_name = serializers.CharField(source='reporter.get_full_name', read_only=True)
    missing_person_name = serializers.CharField(
        source='missing_person.name',
        read_only=True
    )
    verified_by_name = serializers.CharField(
        source='verified_by.get_full_name',
        read_only=True
    )

    class Meta:
        model = Sighting
        fields = '__all__'
        read_only_fields = (
            'reporter', 'facial_match_confidence',
            'ml_analysis_results', 'created_at', 'updated_at',
            'ip_address', 'device_info'
        )

    def create(self, validated_data):
        # Add IP address and device info from request
        request = self.context.get('request')
        if request:
            validated_data['ip_address'] = self.get_client_ip(request)
            validated_data['device_info'] = self.get_device_info(request)
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