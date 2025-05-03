from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import FileExtensionValidator


class SurveillanceFootage(models.Model):
    FOOTAGE_TYPE_CHOICES = [
        ('CCTV', 'CCTV Camera'),
        ('DASHCAM', 'Dashboard Camera'),
        ('MOBILE', 'Mobile Recording'),
        ('OTHER', 'Other Source')
    ]

    title = models.CharField(max_length=255)
    footage_type = models.CharField(max_length=10, choices=FOOTAGE_TYPE_CHOICES)
    file = models.FileField(
        upload_to='surveillance_footage/',
        validators=[FileExtensionValidator(allowed_extensions=['mp4', 'avi', 'mov'])]
    )
    location_name = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    timestamp = models.DateTimeField()
    duration = models.DurationField()
    uploaded_by = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    frame_rate = models.IntegerField(default=30)
    resolution = models.CharField(max_length=20)  # e.g., "1920x1080"

    class Meta:
        indexes = [
            models.Index(fields=['latitude', 'longitude']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['processed'])
        ]
