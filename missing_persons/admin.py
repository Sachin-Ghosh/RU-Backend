from django.contrib import admin

# Register your models here.
# missing_persons/admin.py

from django.contrib import admin
from .models import MissingPerson, MissingPersonDocument

class MissingPersonDocumentInline(admin.TabularInline):
    model = MissingPersonDocument
    extra = 1
    readonly_fields = ('uploaded_by', 'uploaded_at')

@admin.register(MissingPerson)
class MissingPersonAdmin(admin.ModelAdmin):
    list_display = (
        'case_number', 'name', 'age_when_missing',
        'last_seen_date', 'status', 'priority_level','reporter', 'assigned_officer', 'assigned_ngo'
    )
    list_filter = (
        'status', 'gender', 'priority_level',
        'created_at', 'last_seen_date','reporter', 'assigned_officer', 'assigned_ngo'
    )
    search_fields = (
        'name', 'case_number', 'fir_number',
        'last_seen_location', 'description','reporter', 'assigned_officer', 'assigned_ngo'
    )
    readonly_fields = (
        'case_number', 'facial_encoding',
        'created_at', 'updated_at', 'reporter', 'assigned_officer', 'assigned_ngo'
    )
    actions = ['assign_to_officer', 'assign_to_ngo', 'close_cases']
    inlines = [MissingPersonDocumentInline]

    fieldsets = (
        ('Basic Information', {
            'fields': (
                'case_number', 'name', 'age_when_missing',
                'date_of_birth', 'gender', 'blood_group',
                'nationality'
            )
        }),
        ('Physical Characteristics', {
            'fields': (
                'height', 'weight', 'complexion',
                'identifying_marks', 'physical_attributes'
            )
        }),
        ('Images & Biometric', {
            'fields': (
                'recent_photo', 'additional_photos',
                'facial_encoding'
            ),
            'classes': ('collapse',)
        }),
        ('Missing Details', {
            'fields': (
                'last_seen_location', 'last_seen_date',
                'last_seen_details', 'last_seen_wearing',
                'possible_locations'
            )
        }),
        ('Case Information', {
            'fields': (
                'fir_number', 'status', 'priority_level',
                'reporter', 'assigned_officer', 'assigned_ngo'
            )
        }),
        ('Medical Information', {
            'fields': ('medical_conditions', 'medications'),
            'classes': ('collapse',)
        }),
        ('Contact Information', {
            'fields': (
                'emergency_contact_name', 'emergency_contact_phone',
                'emergency_contact_relation', 'secondary_contact_name',
                'secondary_contact_phone'
            )
        }),
        ('Family Information', {
            'fields': ('family_group', 'family_member'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'last_modified_by'),
            'classes': ('collapse',)
        }),

    )

    def assign_to_officer(self, request, queryset):
        officer = request.user if request.user.role == 'LAW_ENFORCEMENT' else None
        if officer:
            queryset.update(assigned_officer=officer)
    assign_to_officer.short_description = "Assign to current officer"

    def assign_to_ngo(self, request, queryset):
        ngo = request.user if request.user.role == 'NGO' else None
        if ngo:
            queryset.update(assigned_ngo=ngo)
    assign_to_ngo.short_description = "Assign to current NGO"

    def close_cases(self, request, queryset):
        queryset.update(status='CLOSED')
    close_cases.short_description = "Close selected cases"
    
    def save_model(self, request, obj, form, change):
        if not change:  # If creating new object
            obj.reporter = request.user
        obj.last_modified_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(MissingPersonDocument)
class MissingPersonDocumentAdmin(admin.ModelAdmin):
    list_display = (
        'missing_person', 'document_type',
        'uploaded_by', 'uploaded_at',   
    )
    list_filter = ('document_type', 'uploaded_at')
    search_fields = ('missing_person__name', 'description')
    readonly_fields = ('uploaded_by', 'uploaded_at')

