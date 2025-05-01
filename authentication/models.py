from django.db import models
from accounts.models import User


class AuthenticationLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='auth_logs')
    timestamp = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=50)
    ip_address = models.GenericIPAddressField()
    device_info = models.JSONField()
    status = models.CharField(max_length=50)
    failure_reason = models.TextField(blank=True)

class BiometricAuth(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='biometric_auths')
    auth_type = models.CharField(max_length=50)
    biometric_data = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(null=True)
    is_active = models.BooleanField(default=True)

class OTPVerification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otp_verifications')
    otp = models.CharField(max_length=6)
    purpose = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True)