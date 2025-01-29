from django.contrib import admin

# Register your models here.
# sightings/admin.py

from django.contrib import admin
from .models import Sighting

@admin.register(Sighting)
class SightingAdmin(admin.ModelAdmin):
    list_display = (
        'missing_person', 'location', 'timestamp',
        'verification_status', 'confidence_level'
    )
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

    def save_model(self, request, obj, form, change):
        if not change:  # If creating new object
            obj.reporter = request.user
        super().save_model(request, obj, form, change)