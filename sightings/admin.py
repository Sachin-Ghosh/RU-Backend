from django.contrib import admin

# Register your models here.
# sightings/admin.py

from django.contrib import admin
from .models import Sighting

@admin.register(Sighting)
class SightingAdmin(admin.ModelAdmin):
    list_display = ('id', 'missing_person', 'reporter', 'location', 'timestamp', 'verification_status', 'confidence_level')
    list_filter = (
        'verification_status', 'confidence_level',
        'created_at', 'timestamp'
    )
    search_fields = (
        'missing_person__name', 'location',
        'description', 'verification_notes'
    )
    readonly_fields = (
        'facial_match_confidence', 'created_at',
        'updated_at', 'reporter', 'ip_address'
    )
    actions = ['verify_sightings', 'reject_sightings']

    fieldsets = (
        ('Basic Information', {
            'fields': ('missing_person', 'reporter', 'timestamp')
        }),
        ('Location Details', {
            'fields': (
                'location', 'latitude', 'longitude',
                'location_details', 'direction_headed'
            )
        }),
        ('Sighting Details', {
            'fields': (
                'description', 'wearing',
                'accompanied_by'
            )
        }),
        ('Evidence', {
            'fields': (
                'photo', 'additional_photos',
                'video'
            )
        }),
        ('Verification', {
            'fields': (
                'verification_status', 'verified_by',
                'verification_notes', 'confidence_level'
            )
        }),
        ('ML Analysis', {
            'fields': (
                'facial_match_confidence',
                'ml_analysis_results'
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': (
                'created_at', 'updated_at',
                'ip_address', 'device_info'
            ),
            'classes': ('collapse',)
        }),
    )
    
    def verify_sightings(self, request, queryset):
        queryset.update(verification_status='VERIFIED', verified_by=request.user)
        for sighting in queryset:
            sighting.missing_person.status = 'FOUND' if sighting.confidence_level == 'HIGH' else 'INVESTIGATING'
            sighting.missing_person.save()
    verify_sightings.short_description = "Verify selected sightings"

    def reject_sightings(self, request, queryset):
        queryset.update(verification_status='REJECTED', verified_by=request.user)
    reject_sightings.short_description = "Reject selected sightings"

    def save_model(self, request, obj, form, change):
        if not change:  # If creating new object
            obj.reporter = request.user
        super().save_model(request, obj, form, change)