from django.contrib import admin

# Register your models here.
# authentication/admin.py

from django.contrib import admin
from .models import AuthenticationLog, BiometricAuth, OTPVerification

@admin.register(AuthenticationLog)
class AuthenticationLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'timestamp', 'status', 'ip_address')
    list_filter = ('action', 'status', 'timestamp')
    search_fields = ('user__username', 'ip_address', 'failure_reason')
    readonly_fields = ('timestamp', 'ip_address', 'device_info')

@admin.register(BiometricAuth)
class BiometricAuthAdmin(admin.ModelAdmin):
    list_display = ('user', 'auth_type', 'created_at', 'last_used', 'is_active')
    list_filter = ('auth_type', 'is_active', 'created_at')
    search_fields = ('user__username',)
    readonly_fields = ('created_at', 'last_used')

@admin.register(OTPVerification)
class OTPVerificationAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'purpose', 'created_at',
        'expires_at', 'is_used', 'verified_at'
    )
    list_filter = ('purpose', 'is_used', 'created_at')
    search_fields = ('user__username', 'otp')
    readonly_fields = ('created_at', 'verified_at')