from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator
import uuid
from django.utils.translation import gettext_lazy as _

def document_upload_path(instance, filename):
    return f'documents/organization_docs/{filename}'

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
    is_approved = models.BooleanField(default=False)
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    organization = models.CharField(max_length=200, blank=True)  # For NGO/Law Enforcement
    organization_id = models.CharField(max_length=50, blank=True)  # For verification
    # Add these fields for NGO/Organization
    organization_latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    organization_longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    organization_location = models.CharField(max_length=100, blank=True)
    # verification_documents = models.FileField(upload_to=document_upload_path, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # New fields for UI requirements
    preferred_language = models.CharField(max_length=10, default='en', help_text="e.g., 'en', 'hi', 'ta'")
    notification_preferences = models.JSONField(
        default=dict,
        help_text="e.g., {'push': True, 'email': False, 'sms': True}"
    )

    families = models.ManyToManyField(
        'FamilyGroup',
        through='FamilyMember',
        related_name='members'
    )

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

class FamilyGroup(models.Model):
    name = models.CharField(max_length=100)
    passkey = models.CharField(max_length=12, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_families'
    )

    def __str__(self):
        return f"{self.name} ({self.passkey})"

    @staticmethod
    def generate_passkey():
        """Generate a unique 12-character passkey"""
        return str(uuid.uuid4())[:12].upper()

class FamilyMember(models.Model):
    ROLE_CHOICES = [
        ('ADMIN', 'Admin'),
        ('MEMBER', 'Member'),
    ]

    user = models.ForeignKey('User', on_delete=models.CASCADE)
    family = models.ForeignKey(FamilyGroup, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='MEMBER')
    relationship = models.CharField(max_length=50)  # e.g., 'Father', 'Mother', 'Son'
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'family')

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.relationship} in {self.family.name}"
    
    
class Collaboration(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('ACTIVE', 'Active'),
        ('COMPLETED', 'Completed'),
        ('REJECTED', 'Rejected'),
    ]
    
    initiator = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='initiated_collaborations'
    )
    collaborator = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='received_collaborations'
    )
    missing_person = models.ForeignKey(
        'missing_persons.MissingPerson',  # Assuming you have a MissingPerson model
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        unique_together = ('initiator', 'collaborator', 'missing_person')

class CollaborationMessage(models.Model):
    collaboration = models.ForeignKey(
        Collaboration,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )
    message = models.TextField()
    file_attachment = models.FileField(
        upload_to='collaboration_files/',
        null=True,
        blank=True
    )
    sent_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Message in {self.collaboration} by {self.sender}"

class VerificationDocument(models.Model):
    DOCUMENT_TYPES = (
        ('ORGANIZATION_VERIFICATION', 'Organization Verification'),
        ('IDENTITY_PROOF', 'Identity Proof'),
        ('ADDRESS_PROOF', 'Address Proof'),
        ('OTHER', 'Other')
    )

    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='user_verification_documents'
    )
    document = models.FileField(upload_to='verification_docs/')
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPES)
    description = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='verified_user_documents'
    )
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.user.username} - {self.document_type} - {self.uploaded_at}"

class Notification(models.Model):
    PRIORITY_CHOICES = [
        ('LOW', 'Low Priority'),
        ('MEDIUM', 'Medium Priority'),
        ('HIGH', 'High Priority'),
        ('CRITICAL', 'Critical')
    ]

    ROLE_CHOICES = [
        ('ADMIN', 'Administrator'),
        ('LAW_ENFORCEMENT', 'Law Enforcement'),
        ('NGO', 'NGO Worker'),
        ('CITIZEN', 'Citizen'),
    ]

    title = models.CharField(max_length=255)
    message = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='LOW')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey('User', on_delete=models.CASCADE, related_name='created_notifications')
    target_roles = models.JSONField(
        default=list,
        help_text='List of roles that should receive this notification'
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.priority})"

    def save(self, *args, **kwargs):
        # Ensure target_roles is always a list
        if isinstance(self.target_roles, str):
            self.target_roles = [self.target_roles]
        elif not isinstance(self.target_roles, list):
            self.target_roles = list(self.target_roles)
        super().save(*args, **kwargs)