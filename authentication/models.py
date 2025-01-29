from django.db import models
from accounts.models import User

# Create your models here.

class AuthenticationLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='auth_logs')
    timestamp = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=50)  # login, logout, failed_attempt
    ip_address = models.GenericIPAddressField()
    device_info = models.JSONField()
    status = models.CharField(max_length=50)  # success, failure
    failure_reason = models.TextField(blank=True)

class BiometricAuth(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='biometric_auths')
    auth_type = models.CharField(max_length=50)  # fingerprint, facial, iris
    biometric_data = models.TextField()  # encrypted biometric data
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(null=True)
    is_active = models.BooleanField(default=True)

class OTPVerification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otp_verifications')
    otp = models.CharField(max_length=6)
    purpose = models.CharField(max_length=50)  # registration, login, password_reset
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True)