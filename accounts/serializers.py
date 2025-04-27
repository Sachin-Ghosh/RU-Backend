# accounts/serializers.py

from rest_framework import serializers


from .models import User, AadhaarProfile, FamilyGroup, FamilyMember,Collaboration,CollaborationMessage, Notification

class AadhaarProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = AadhaarProfile
        fields = (
            'id', 'user', 'aadhaar_number_hash', 'name_in_aadhaar', 'dob',
            'gender', 'address_in_aadhaar', 'last_verified',
            'verification_count', 'is_active'
        )
        read_only_fields = (
            'fingerprint_hash', 'document_hash', 'facial_signature',
            'last_verified', 'verification_count'
        )

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)
    aadhaar_profile = AadhaarProfileSerializer(read_only=True)
    verification_documents = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'password', 'first_name', 'middle_name', 'last_name',
            'role', 'phone_number', 'address', 'city', 'state', 'pincode', 'latitude', 'longitude', 
            'dob', 'gender', 'is_verified', 'is_approved', 'profile_picture', 'organization',
            'organization_id', 'created_at', 'updated_at', 'preferred_language', 'notification_preferences',
            'organization_latitude', 'organization_longitude', 'organization_location',
            'aadhaar_profile', 'verification_documents'
        ]
        read_only_fields = ('is_verified', 'is_approved', 'created_at', 'updated_at')
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def create(self, validated_data):
        """Create and return a new user with encrypted password."""
        password = validated_data.pop('password')
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        """Update and return an existing user."""
        password = validated_data.pop('password', None)
        user = super().update(instance, validated_data)
        if password:
            user.set_password(password)
            user.save()
        return user

    def get_verification_documents(self, obj):
        docs = obj.user_verification_documents.all()
        return [{
            'id': doc.id,
            'document_type': doc.document_type,
            'document': self.context['request'].build_absolute_uri(doc.document.url) if doc.document else None,
            'description': doc.description,
            'uploaded_at': doc.uploaded_at,
            'is_verified': doc.is_verified,
            'verified_at': doc.verified_at
        } for doc in docs]

        
class UserDetailSerializer(serializers.ModelSerializer):
    aadhaar_profile = AadhaarProfileSerializer(read_only=True)
    verification_documents = serializers.SerializerMethodField()
    families = serializers.SerializerMethodField()
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'middle_name', 'last_name',
            'phone_number', 'role', 'is_verified', 'is_approved', 'is_active',
            'address', 'city', 'state', 'pincode', 'latitude', 'longitude',
            'organization', 'organization_location', 'organization_latitude',
            'organization_longitude', 'profile_picture', 'aadhaar_profile',
            'verification_documents', 'families'
        ]
    
    def get_verification_documents(self, obj):
        """Get verification documents if they exist"""
        if hasattr(obj, 'verification_documents'):
            return [
                {
                    'id': doc.id,
                    'document_type': doc.document_type,
                    'document': doc.document.url if doc.document else None,
                    'uploaded_at': doc.uploaded_at
                }
                for doc in obj.verification_documents.all()
            ]
        return None

    def get_families(self, obj):
        """Get the user's families"""
        return FamilyGroupSerializer(obj.families.all(), many=True).data

class FamilyGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = FamilyGroup
        fields = ('id', 'name', 'passkey', 'created_at', 'created_by')
        read_only_fields = ('passkey', 'created_at', 'created_by')

class FamilyMemberSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    family = FamilyGroupSerializer(read_only=True)

    class Meta:
        model = FamilyMember
        fields = ('id', 'user', 'family', 'role', 'relationship', 'joined_at')

class UserFamilySerializer(serializers.ModelSerializer):
    families = FamilyGroupSerializer(many=True, read_only=True)
    family_members = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'families', 'family_members')

    def get_family_members(self, obj):
        family_members = FamilyMember.objects.filter(
            family__in=obj.families.all()
        ).exclude(user=obj)
        return FamilyMemberSerializer(family_members, many=True).data


class CollaborationMessageSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)
    
    class Meta:
        model = CollaborationMessage
        fields = ('id', 'sender', 'message', 'file_attachment', 'sent_at')

class CollaborationSerializer(serializers.ModelSerializer):
    initiator = UserSerializer(read_only=True)
    collaborator = UserSerializer(read_only=True)
    messages = CollaborationMessageSerializer(many=True, read_only=True)
    
    class Meta:
        model = Collaboration
        fields = (
            'id', 'initiator', 'collaborator', 'missing_person',
            'status', 'created_at', 'updated_at', 'notes', 'messages'
        )

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'title', 'message', 'priority', 'created_at', 'expires_at']

class DashboardSerializer(serializers.Serializer):
    user = UserSerializer()
    notifications = NotificationSerializer(many=True)
    statistics = serializers.DictField()
    recent_activity = serializers.ListField()