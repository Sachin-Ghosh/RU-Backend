# accounts/serializers.py

from rest_framework import serializers
from .models import User, AadhaarProfile

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)
    
    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'password', 'first_name', 'middle_name', 'last_name',
            'role', 'phone_number', 'address', 'city', 'state', 'pincode', 'latitude', 'longitude', 'dob', 'gender', 
            'is_verified', 'profile_picture', 'organization',
            'organization_id', 'created_at', 'updated_at'
        )
        read_only_fields = ('is_verified', 'created_at', 'updated_at')
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

    class Meta:
        model = User
        fields = '__all__'
        read_only_fields = ('is_verified', 'created_at', 'updated_at')
