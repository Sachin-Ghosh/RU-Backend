# from django.contrib import admin

# Register your models here.
# accounts/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, AadhaarProfile, FamilyGroup, FamilyMember

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = (
        'username', 'email', 'first_name', 'last_name',
        'role', 'is_verified', 'created_at', 'is_approved', 'preferred_language'
    )
    list_filter = ('role', 'is_verified', 'created_at', 'city', 'state', 'is_approved', 'preferred_language')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'phone_number')
    ordering = ('-created_at',)
    actions = ['approve_users', 'suspend_users']
    
    def approve_users(self, request, queryset):
        queryset.update(is_approved=True)
        queryset.update(is_verified=True)
    approve_users.short_description = "Approve selected users"

    def suspend_users(self, request, queryset):
        queryset.update(is_approved=False)
        queryset.update(is_verified=False)
    suspend_users.short_description = "Suspend selected users"
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {
            'fields': (
                'first_name', 'middle_name', 'last_name', 'email', 'phone_number',
                'profile_picture', 'dob', 'gender', 'preferred_language'
            )
        }),
        ('Address', {
            'fields': ('address', 'city', 'state', 'pincode', 'latitude', 'longitude')
        }),
        ('Organization', {
            'fields': ('role', 'organization', 'organization_id')
        }),
        ('Status', {
            'fields': ('is_verified', 'is_approved', 'is_active', 'is_staff', 'is_superuser')
        }),
        ('Notification Preferences', {
            'fields': ('notification_preferences',)
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
    
class FamilyGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'passkey', 'created_at', 'created_by')
    search_fields = ('name', 'passkey', 'created_by__username')
    list_filter = ('created_at', 'created_by')

admin.site.register(FamilyGroup, FamilyGroupAdmin)

class FamilyMemberAdmin(admin.ModelAdmin):
    list_display = ('user', 'family', 'role', 'relationship', 'joined_at')
    search_fields = ('user__username', 'family__name')
    list_filter = ('joined_at', 'role')

admin.site.register(FamilyMember, FamilyMemberAdmin)

