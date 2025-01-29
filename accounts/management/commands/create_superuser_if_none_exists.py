from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import os

class Command(BaseCommand):
    help = 'Creates a superuser if none exists'

    def handle(self, *args, **options):
        User = get_user_model()
        if User.objects.filter(is_superuser=True).count() == 0:
            username = os.getenv('DJANGO_SUPERUSER_USERNAME')
            email = os.getenv('DJANGO_SUPERUSER_EMAIL')
            password = os.getenv('DJANGO_SUPERUSER_PASSWORD')
            
            if not all([username, email, password]):
                self.stdout.write(self.style.ERROR('Environment variables not properly set'))
                return
            
            try:
                superuser = User.objects.create_superuser(
                    username=username,
                    email=email,
                    password=password
                )
                self.stdout.write(self.style.SUCCESS(f'Superuser {username} created successfully!'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Failed to create superuser: {str(e)}'))
        else:
            self.stdout.write(self.style.WARNING('Superuser already exists.'))