# accounts/serializers.py

from rest_framework import serializers
from .models import User, AadhaarProfile, FamilyGroup, FamilyMember

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)
    
    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'password', 'first_name', 'middle_name', 'last_name',
            'role', 'phone_number', 'address', 'city', 'state', 'pincode', 'latitude', 'longitude', 'dob', 'gender', 
            'is_verified', 'is_approved', 'profile_picture', 'organization',
            'organization_id', 'created_at', 'updated_at', 'preferred_language', 'notification_preferences'
        )
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
        
class UserDetailSerializer(serializers.ModelSerializer):
    aadhaar_profile = AadhaarProfileSerializer(read_only=True)
    families = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = '__all__'
        read_only_fields = ('is_verified', 'created_at', 'updated_at')
        
    def get_families(self, obj):
        family_members = FamilyMember.objects.filter(user=obj)
        return FamilyMemberSerializer(family_members, many=True).data

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
