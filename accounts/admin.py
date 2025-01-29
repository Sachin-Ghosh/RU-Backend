# from django.contrib import admin

# Register your models here.
# accounts/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, AadhaarProfile

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = (
        'username', 'email', 'first_name', 'last_name',
        'role', 'is_verified', 'created_at'
    )
    list_filter = ('role', 'is_verified', 'created_at', 'city', 'state')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'phone_number')
    ordering = ('-created_at',)
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {
            'fields': (
                'first_name', 'middle_name', 'last_name', 'email', 'phone_number',
                'profile_picture', 'dob', 'gender'
            )

        }),
        ('Address', {
            'fields': ('address', 'city', 'state', 'pincode', 'latitude', 'longitude')
        }),
        ('Organization', {
            'fields': ('role', 'organization', 'organization_id')
        }),
        ('Status', {
            'fields': ('is_verified', 'is_active', 'is_staff', 'is_superuser')
        }),
        ('Important dates', {
            'fields': ('last_login', 'date_joined')
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2'),
        }),
    )

@admin.register(AadhaarProfile)
class AadhaarProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'name_in_aadhaar',
        'verification_count', 'is_active', 'last_verified'
    )
    list_filter = ('is_active', 'gender', 'last_verified')
    search_fields = ( 'name_in_aadhaar', 'user__username')
    readonly_fields = ('verification_count', 'last_verified')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'aadhaar_number_hash', 'name_in_aadhaar', 'dob', 'gender')
        }),
        ('Address', {
            'fields': ('address_in_aadhaar',)
        }),
        ('Verification', {
            'fields': ('is_active', 'verification_count', 'last_verified')
        }),
        ('Biometric Data', {
            'fields': ('document_hash', 'fingerprint_hash', 'facial_signature'),
            'classes': ('collapse',),
        }),
    )