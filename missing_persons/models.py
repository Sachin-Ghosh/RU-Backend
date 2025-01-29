from django.db import models
# from django.contrib.postgres.fields import ArrayField
from accounts.models import User

class MissingPerson(models.Model):
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('MISSING', 'Missing'),
        ('FOUND', 'Found'),
        ('INVESTIGATING', 'Under Investigation'),
        ('RESOLVED', 'Case Resolved'),
    ]

    BLOOD_GROUP_CHOICES = [
        ('A+', 'A Positive'),
        ('A-', 'A Negative'),
        ('B+', 'B Positive'),
        ('B-', 'B Negative'),
        ('O+', 'O Positive'),
        ('O-', 'O Negative'),
        ('AB+', 'AB Positive'),
        ('AB-', 'AB Negative'),
    ]

    REPORTER_TYPE_CHOICES = [
        ('SELF', 'Self Reported'),
        ('FAMILY', 'Family Member'),
        ('POLICE', 'Police Officer'),
        ('NGO', 'NGO Worker'),
        ('OTHER', 'Other')
    ]

    # Basic Information
    name = models.CharField(max_length=100)
    age_when_missing = models.IntegerField()
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    blood_group = models.CharField(max_length=3, choices=BLOOD_GROUP_CHOICES, blank=True, null=True)
    nationality = models.CharField(max_length=50, default='Indian')
    
    # Physical Characteristics
    height = models.FloatField(help_text='Height in cm')
    weight = models.FloatField(help_text='Weight in kg')
    complexion = models.CharField(max_length=50)
    identifying_marks = models.TextField(blank=True)
    physical_attributes = models.JSONField(default=dict)  # Store additional attributes
    
    # Images and Biometric Data
    recent_photo = models.ImageField(upload_to='missing_persons/photos/')
    additional_photos = models.JSONField(default=list)  # Store multiple photo URLs
    facial_encoding = models.JSONField(null=True)  # Store facial recognition data
    
    # Missing Details
    last_seen_location = models.CharField(max_length=255)
    last_seen_date = models.DateTimeField()
    last_seen_details = models.TextField()
    last_seen_wearing = models.TextField()
    possible_locations = models.JSONField(default=list)
    
    # Case Details
    case_number = models.CharField(max_length=50, unique=True)
    fir_number = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='MISSING')
    priority_level = models.IntegerField(default=1)  # 1 (low) to 5 (high)
    
    # Relations
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reported_cases')
    assigned_officer = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='assigned_cases'
    )
    
    # Medical Information
    medical_conditions = models.TextField(blank=True)
    medications = models.TextField(blank=True)
    
    # Contact Information
    emergency_contact_name = models.CharField(max_length=100)
    emergency_contact_phone = models.CharField(max_length=15)
    emergency_contact_relation = models.CharField(max_length=50)
    secondary_contact_name = models.CharField(max_length=100, blank=True)
    secondary_contact_phone = models.CharField(max_length=15, blank=True)
    
    # Timestamps and Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_modified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='modified_cases'
    )
    
    # Family Information
    family_group = models.ForeignKey(
        'accounts.FamilyGroup',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    family_member = models.ForeignKey(
        'accounts.FamilyMember',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Additional fields for enhanced reporting
    is_registered_user = models.BooleanField(default=False)
    registered_user = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='missing_profile'
    )
    reporter_type = models.CharField(
        max_length=20,
        choices=REPORTER_TYPE_CHOICES,
        default='OTHER'
    )
    last_known_location = models.JSONField(
        default=dict,
        help_text='Store location history with timestamps'
    )
    aadhaar_number_hash = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        db_index=True
    )
    facial_match_confidence = models.FloatField(
        default=0.0,
        help_text='Confidence score from facial recognition'
    )
    
    class Meta:
        verbose_name = 'Missing Person'

        verbose_name_plural = 'Missing Persons'
        ordering = ['-created_at']

class MissingPersonDocument(models.Model):
    DOCUMENT_TYPES = [
        ('POLICE_REPORT', 'Police Report'),
        ('ID_PROOF', 'ID Proof'),
        ('MEDICAL_RECORD', 'Medical Record'),
        ('OTHER', 'Other')
    ]

    missing_person = models.ForeignKey(
        MissingPerson,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    document_type = models.CharField(
        max_length=20,
        choices=DOCUMENT_TYPES
    )
    document = models.FileField(
        upload_to='missing_persons/documents/',
        null=True,
        blank=True
    )
    description = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.document_type} - {self.missing_person.name}"