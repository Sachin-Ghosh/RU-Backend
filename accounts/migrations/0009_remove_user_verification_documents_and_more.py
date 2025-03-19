# Generated by Django 5.1.5 on 2025-03-19 11:01

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0008_user_verification_documents'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='verification_documents',
        ),
        migrations.CreateModel(
            name='VerificationDocument',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('document', models.FileField(upload_to='verification_docs/')),
                ('document_type', models.CharField(choices=[('ORGANIZATION_VERIFICATION', 'Organization Verification'), ('IDENTITY_PROOF', 'Identity Proof'), ('ADDRESS_PROOF', 'Address Proof'), ('OTHER', 'Other')], max_length=50)),
                ('description', models.TextField(blank=True)),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('is_verified', models.BooleanField(default=False)),
                ('verified_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_verification_documents', to=settings.AUTH_USER_MODEL)),
                ('verified_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='verified_user_documents', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-uploaded_at'],
            },
        ),
    ]
