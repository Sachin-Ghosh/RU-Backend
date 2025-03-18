from rest_framework import serializers
from .models import MissingPerson, MissingPersonDocument
from accounts.models import FamilyMember
from accounts.serializers import FamilyMemberSerializer, FamilyGroupSerializer

class MissingPersonDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MissingPersonDocument
        fields = ['id', 'document_type', 'description', 'file', 'uploaded_at']

# class FamilyMemberSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = FamilyMember
#         fields = [
#             'id', 'name', 'relationship', 'age', 'gender',
#             'contact_number', 'alternate_contact',
#             'address', 'email', 'aadhaar_number'
#         ]

class MissingPersonSerializer(serializers.ModelSerializer):
    medical_conditions = serializers.CharField(required=False, allow_blank=True)
    medications = serializers.CharField(required=False, allow_blank=True)
    family_group = FamilyGroupSerializer(read_only=True)
    family_members = serializers.SerializerMethodField()
    documents = MissingPersonDocumentSerializer(many=True, read_only=True)
    recent_photo = serializers.ImageField(required=False, allow_null=True)
    distance = serializers.SerializerMethodField()
    # reporter_name = serializers.CharField(source='reporter.get_full_name', read_only=True)
    # assigned_officer_name = serializers.CharField(
    #     source='assigned_officer.get_full_name',
    #     read_only=True
    # )
    # age_current = serializers.SerializerMethodField()
    # physical_attributes = serializers.JSONField(required=False)
    # last_seen_wearing = serializers.CharField(required=False)
    # possible_locations = serializers.JSONField(required=False)
    # additional_photos = serializers.JSONField(required=False)

    class Meta:
        model = MissingPerson
        fields = [
            'id', 'case_number', 'name', 'age_when_missing', 'date_of_birth',
            'gender', 'blood_group', 'nationality', 'height', 'weight',
            'complexion', 'identifying_marks', 'physical_attributes','recent_photo', 'additional_photos',
            'last_seen_location', 'last_seen_date', 'last_seen_details',
            'last_seen_wearing', 'possible_locations', 'fir_number', 'poster_image',
            'status', 'priority_level', 'medical_conditions', 'medications',
            'emergency_contact_name', 'emergency_contact_phone',
            'emergency_contact_relation', 'secondary_contact_name',
            'secondary_contact_phone', 'reporter', 'assigned_officer', 'assigned_ngo', 'documents', 'recent_photo',
            'last_known_latitude', 'last_known_longitude',
            'aadhaar_number', 'aadhaar_photo', 'family_group', 
            'distance', 'family_members','aadhaar_number_hash','reporter_type'
            'created_at', 'updated_at'
        ]
        read_only_fields = ('case_number', 'reporter', 'created_at', 'updated_at', 'documents')

    def to_internal_value(self, data):
        # Keep medical conditions and medications as they are
        data = data.copy()
        return super().to_internal_value(data)

    def get_age_current(self, obj):
        from datetime import date
        if obj.date_of_birth:
            today = date.today()
            return (
                today.year - obj.date_of_birth.year -
                ((today.month, today.day) < 
                 (obj.date_of_birth.month, obj.date_of_birth.day))
            )
        return None

    def get_distance(self, obj):
        if hasattr(obj, 'distance'):
            return f"{obj.distance:.5f} km"
        return None

    def get_family_members(self, obj):
        if obj.family_group:
            family_members = FamilyMember.objects.filter(family_group=obj.family_group)
            return FamilyMemberSerializer(family_members, many=True).data
        return []