from rest_framework import serializers
from .models import MissingPerson, MissingPersonDocument

class MissingPersonDocumentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)

    class Meta:
        model = MissingPersonDocument
        fields = '__all__'
        read_only_fields = ('uploaded_by', 'uploaded_at')

class MissingPersonSerializer(serializers.ModelSerializer):
    documents = MissingPersonDocumentSerializer(many=True, read_only=True)
    reporter_name = serializers.CharField(source='reporter.get_full_name', read_only=True)
    assigned_officer_name = serializers.CharField(
        source='assigned_officer.get_full_name',
        read_only=True
    )
    age_current = serializers.SerializerMethodField()
    # physical_attributes = serializers.JSONField(required=False)
    # last_seen_wearing = serializers.CharField(required=False)
    # possible_locations = serializers.JSONField(required=False)
    # additional_photos = serializers.JSONField(required=False)



    class Meta:
        model = MissingPerson
        fields = '__all__'
        read_only_fields = ('case_number', 'reporter', 'created_at', 'updated_at')

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

    # def to_internal_value(self, data):
    #     # Convert string arrays to proper format
    #     for field in ['medical_conditions', 'medications']:
    #         if field in data and isinstance(data[field], str):
    #             data[field] = [item.strip() for item in data[field].split(',')]
    #     return super().to_internal_value(data)

    def create(self, validated_data):
        # Generate unique case number
        import uuid
        validated_data['case_number'] = f'MP{uuid.uuid4().hex[:8].upper()}'
        
        # Set reporter as current user
        validated_data['reporter'] = self.context['request'].user
        
        return super().create(validated_data)