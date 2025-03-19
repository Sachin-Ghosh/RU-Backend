from django.db import models
from django.conf import settings
from accounts.models import User


class Sighting(models.Model):
    VERIFICATION_STATUS = [
        ('PENDING', 'Pending Verification'),
        ('VERIFIED', 'Verified'),
        ('REJECTED', 'Rejected'),
        ('INVESTIGATING', 'Under Investigation'),
    ]

    CONFIDENCE_LEVELS = [
        ('HIGH', 'High Confidence'),
        ('MEDIUM', 'Medium Confidence'),
        ('LOW', 'Low Confidence'),
    ]
    
    LOCATION_TYPES = [
        ('INDOOR', 'Indoor'),
        ('OUTDOOR', 'Outdoor'),
        ('VEHICLE', 'Vehicle'),
        ('PUBLIC_TRANSPORT', 'Public Transport'),
        ('OTHER', 'Other')
    ]

    CROWD_DENSITY = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('VERY_HIGH', 'Very High'),
        ('UNKNOWN', 'Unknown'),
    ]

    COMPANION_TYPES = [
        ('ALONE', 'Alone'),
        ('WITH_ADULT', 'With Adult'),
        ('WITH_CHILDREN', 'With Children'),
        ('WITH_GROUP', 'With Group'),
        ('UNSURE', 'Unsure')
    ]

    missing_person = models.ForeignKey(
        'missing_persons.MissingPerson',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sightings'
    )
    reporter = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='reported_sightings',
        null=True,  # Allow anonymous reports
        blank=True
    )
    
    # Add fields for anonymous reporters
    reporter_name = models.CharField(max_length=100, blank=True)
    reporter_contact = models.CharField(max_length=100, blank=True)
    
    # Location Information
    location = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_details = models.TextField()
    
    # Sighting Details
    timestamp = models.DateTimeField()
    description = models.TextField()
    wearing = models.TextField(blank=True)
    accompanied_by = models.TextField(blank=True)
    direction_headed = models.CharField(max_length=100, blank=True)
    
    # New fields
    location_type = models.CharField(max_length=20, choices=LOCATION_TYPES, default='UNKNOWN')
    crowd_density = models.CharField(max_length=20, choices=CROWD_DENSITY, default='UNKNOWN')
    observed_behavior = models.TextField(blank=True)
    confidence_level_numeric = models.FloatField(default=0)
    willing_to_contact = models.BooleanField(default=True)
    companions = models.CharField(max_length=20, choices=COMPANION_TYPES, default='UNSURE')
    
    # Evidence
    photo = models.ImageField(upload_to='sightings/photos/', null=True, blank=True)
    additional_photos = models.JSONField(default=list)
    video = models.FileField(upload_to='sightings/videos/', null=True, blank=True)
    
    # Verification
    verification_status = models.CharField(
        max_length=20,
        choices=VERIFICATION_STATUS,
        default='PENDING'
    )
    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_sightings'
    )
    verification_notes = models.TextField(blank=True)
    confidence_level = models.CharField(
        max_length=10,
        choices=CONFIDENCE_LEVELS,
        default='MEDIUM'
    )
    
    # ML Analysis Results
    facial_match_confidence = models.FloatField(null=True, blank=True)
    ml_analysis_results = models.JSONField(default=dict)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    device_info = models.JSONField(default=dict)
    
    # New Fields for UI
    is_notified = models.BooleanField(default=False)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Sighting'
        verbose_name_plural = 'Sightings'