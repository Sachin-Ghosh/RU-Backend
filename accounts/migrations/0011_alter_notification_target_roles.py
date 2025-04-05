# Generated by Django 5.1.5 on 2025-04-03 09:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0010_notification'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='target_roles',
            field=models.JSONField(default=list, help_text='List of roles that should receive this notification. Choose from: ADMIN, LAW_ENFORCEMENT, NGO, CITIZEN'),
        ),
    ]
