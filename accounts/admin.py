# from django.contrib import admin

# Register your models here.
# accounts/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, AadhaarProfile, FamilyGroup, FamilyMember,Collaboration,CollaborationMessage, Notification
from django import forms

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

@admin.register(Collaboration)
class CollaborationAdmin(admin.ModelAdmin):
    list_display = ('id', 'initiator', 'collaborator', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('initiator__username', 'collaborator__username')

@admin.register(CollaborationMessage)
class CollaborationMessageAdmin(admin.ModelAdmin):
    list_display = ('collaboration', 'sender', 'sent_at')
    list_filter = ('sent_at',)
    search_fields = ('message', 'sender__username')

class NotificationAdminForm(forms.ModelForm):
    target_roles = forms.MultipleChoiceField(
        choices=Notification.ROLE_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        help_text='Select which user roles should receive this notification'
    )

    class Meta:
        model = Notification
        fields = '__all__'

    def clean_target_roles(self):
        """Convert selected roles to list for JSON field"""
        return list(self.cleaned_data['target_roles'])

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    form = NotificationAdminForm
    list_display = ['title', 'priority', 'created_at', 'expires_at', 'is_active']
    list_filter = ['priority', 'is_active']
    search_fields = ['title', 'message']
    readonly_fields = ['created_at']
    fieldsets = (
        (None, {
            'fields': ('title', 'message', 'priority')
        }),
        ('Target Audience', {
            'fields': ('target_roles',),
            'description': 'Select which user roles should receive this notification'
        }),
        ('Settings', {
            'fields': ('is_active', 'expires_at', 'created_by')
        })
    )

    def save_model(self, request, obj, form, change):
        if not change:  # If creating new notification
            obj.created_by = request.user
        super().save_model(request, obj, form, change)