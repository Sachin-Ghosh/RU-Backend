from django.db import models

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

    missing_person = models.ForeignKey('missing_persons.MissingPerson', on_delete=models.CASCADE)
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reported_sightings')
    
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

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Sighting'
        verbose_name_plural = 'Sightings'