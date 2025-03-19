# sightings/serializers.py

from rest_framework import serializers

from sightings.services import SightingService
from .models import Sighting
from missing_persons.models import MissingPerson
from missing_persons.serializers import MissingPersonSerializer

class SightingSerializer(serializers.ModelSerializer):
    reporter_name = serializers.CharField(required=False, allow_blank=True)
    reporter_contact = serializers.CharField(required=False, allow_blank=True)
    missing_person_name = serializers.SerializerMethodField()
    verified_by_name = serializers.SerializerMethodField()
    missing_person = MissingPersonSerializer(read_only=True)
    missing_person_id = serializers.PrimaryKeyRelatedField(
        queryset=MissingPerson.objects.all(),
        source='missing_person',
        write_only=True,
        required=False,  # Allow cases where missing_person isn't provided
        allow_null=True
    )
    photo = serializers.ImageField(required=False)
    
    class Meta:
        model = Sighting
        fields = [
            'id', 'missing_person', 'missing_person_id', 'missing_person_name',
            'reporter', 'reporter_name', 'reporter_contact', 'timestamp',
            'location', 'latitude', 'longitude', 'location_details',
            'direction_headed', 'description', 'wearing', 'accompanied_by',
            'photo', 'additional_photos', 'video', 'verification_status',
            'verified_by', 'verified_by_name', 'verification_notes',
            'confidence_level', 'facial_match_confidence', 'ml_analysis_results',
            'created_at', 'updated_at', 'ip_address', 'device_info',
            'is_notified', 'location_type', 'crowd_density', 'observed_behavior',
            'confidence_level_numeric', 'willing_to_contact', 'companions'
        ]
        read_only_fields = [
            'reporter', 'facial_match_confidence',
            'created_at', 'updated_at', 'ip_address',
            'device_info', 'verified_by', 'verified_by_name',
            'missing_person', 'reporter_name', 'is_notified','facial_match_confidence'
        ]
        
    def validate_confidence_level_numeric(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError("Confidence level must be between 0 and 100")
        return value

    def get_reporter_name(self, obj):
        if obj.reporter:
            return obj.reporter.get_full_name() or f"{obj.reporter.first_name} {obj.reporter.last_name}".strip()
        return obj.reporter_name or "Anonymous"

    def get_reporter_contact(self, obj):
        if obj.reporter:
            return obj.reporter.phone_number
        return ""

    def get_missing_person_name(self, obj):
        if obj.missing_person:
            return obj.missing_person.name
        return None

    def get_verified_by_name(self, obj):
        if obj.verified_by:
            return f"{obj.verified_by.first_name} {obj.verified_by.last_name}".strip()
        return None

    def create(self, validated_data):
        request = self.context.get('request')
        missing_person_id = validated_data.pop('missing_person_id', None)

        if request:
            validated_data['ip_address'] = self.get_client_ip(request)
            validated_data['device_info'] = self.get_device_info(request)
            
        # Set reporter from authenticated user
        if request and request.user.is_authenticated:
            validated_data['reporter'] = request.user
            validated_data['reporter_name'] = request.user.get_full_name() or f"{request.user.first_name} {request.user.last_name}".strip()
            validated_data['reporter_contact'] = request.user.phone_number or ""

        # Create sighting instance
        instance = super().create(validated_data)

        if 'missing_person' in self.initial_data and 'missing_person_id' not in validated_data:
            try:
                missing_person_id = self.initial_data['missing_person']
                validated_data['missing_person'] = MissingPerson.objects.get(id=missing_person_id)
            except (MissingPerson.DoesNotExist, ValueError):
                raise serializers.ValidationError({"missing_person": "Invalid missing person ID"})
            
        # Handle missing person association
        if missing_person_id:
            try:
                missing_person = MissingPerson.objects.get(id=missing_person_id)
                instance.missing_person = missing_person
                instance.save()
            except MissingPerson.DoesNotExist:
                pass

        # Process photo matching if photo exists
        if instance.photo and not instance.missing_person:
            sighting_service = SightingService()
            matches = sighting_service.check_against_missing_persons(instance)
            
            if matches:
                # Update with matched person
                matched_person = matches[0]['person']
                instance.missing_person = matched_person
                instance.confidence_level = 'HIGH'
                instance.facial_match_confidence = matches[0]['confidence']
                instance.save()
            else:
                # Create new unidentified person case
                sighting_service.handle_unmatched_sighting(instance)

        return instance

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