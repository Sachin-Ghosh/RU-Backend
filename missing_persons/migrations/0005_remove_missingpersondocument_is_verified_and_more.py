# Generated by Django 5.1.5 on 2025-01-29 14:03

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('missing_persons', '0004_missingperson_aadhaar_number_hash_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveField(
            model_name='missingpersondocument',
            name='is_verified',
        ),
        migrations.AlterField(
            model_name='missingpersondocument',
            name='document',
            field=models.FileField(blank=True, null=True, upload_to='missing_persons/documents/'),
        ),
        migrations.AlterField(
            model_name='missingpersondocument',
            name='document_type',
            field=models.CharField(choices=[('POLICE_REPORT', 'Police Report'), ('ID_PROOF', 'ID Proof'), ('MEDICAL_RECORD', 'Medical Record'), ('OTHER', 'Other')], max_length=20),
        ),
        migrations.AlterField(
            model_name='missingpersondocument',
            name='uploaded_by',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL),
        ),
    ]
