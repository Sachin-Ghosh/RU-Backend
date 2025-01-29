from django.core.management.base import BaseCommand
from missing_persons.services import BiometricService

class Command(BaseCommand):
    help = 'Train biometric models with dataset'

    def add_arguments(self, parser):
        parser.add_argument('dataset_path', type=str, help='Path to the dataset directory')

    def handle(self, *args, **options):
        dataset_path = options['dataset_path']
        
        self.stdout.write('Training biometric models...')
        service = BiometricService()
        service.train_models(dataset_path)
        self.stdout.write(self.style.SUCCESS('Successfully trained models')) 