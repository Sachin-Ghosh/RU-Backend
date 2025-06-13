from rest_framework import serializers
from .models import AuthenticationLog, BiometricAuth, OTPVerification

class AuthenticationLogSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = AuthenticationLog
        fields = '__all__'
        read_only_fields = ('user', 'timestamp', 'ip_address', 'device_info')

class BiometricAuthSerializer(serializers.ModelSerializer):
    class Meta:
        model = BiometricAuth
        fields = (
            'id', 'user', 'auth_type', 'created_at',
            'last_used', 'is_active'
        )
        read_only_fields = ('created_at', 'last_used')
        extra_kwargs = {
            'biometric_data': {'write_only': True}
        }

class OTPVerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = OTPVerification
        fields = (
            'id', 'user', 'purpose', 'created_at',
            'expires_at', 'is_used', 'verified_at'
        )
        read_only_fields = (
            'otp', 'created_at', 'expires_at',
            'is_used', 'verified_at'
        )