from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator

class User(AbstractUser):
    ROLE_CHOICES = [
        ('ADMIN', 'Administrator'),
        ('LAW_ENFORCEMENT', 'Law Enforcement'),
        ('NGO', 'NGO Worker'),
        ('CITIZEN', 'Citizen'),
    ]

    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='CITIZEN')
    phone_number = models.CharField(validators=[phone_regex], max_length=17, blank=True)
    address = models.TextField(blank=True)
    dob = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=1,null=True,blank=True, choices=[('M', 'Male'), ('F', 'Female'), ('O', 'Other')])
    # location = models.CharField(max_length=100, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    pincode = models.CharField(max_length=6, blank=True)
    is_verified = models.BooleanField(default=False)

    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    organization = models.CharField(max_length=200, blank=True)  # For NGO/Law Enforcement
    organization_id = models.CharField(max_length=50, blank=True)  # For verification
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'

class AadhaarProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='aadhaar_profile')
    aadhaar_number_hash = models.CharField(max_length=64, null=True, blank=True)  # Store hashed Aadhaar number
    name_in_aadhaar = models.CharField(max_length=100)
    dob = models.DateField()
    gender = models.CharField(max_length=1, choices=[('M', 'Male'), ('F', 'Female'), ('O', 'Other')])
    address_in_aadhaar = models.TextField()
    
    # Biometric hashes
    document_hash = models.CharField(max_length=64, null=True, blank=True)  # Hash of Aadhaar card image
    fingerprint_hash = models.CharField(max_length=64, null=True, blank=True)
    facial_signature = models.CharField(max_length=64, null=True, blank=True)
    
    # Metadata
    last_verified = models.DateTimeField(auto_now=True)
    verification_count = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    blockchain_reference = models.CharField(max_length=64, null=True)  # Reference to blockchain entry

    class Meta:
        verbose_name = 'Aadhaar Profile'
        verbose_name_plural = 'Aadhaar Profiles'