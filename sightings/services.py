from deepface import DeepFace
from django.core.mail import send_mail
from django.conf import settings
from .models import Sighting
from missing_persons.models import MissingPerson

class SightingService:
    def process_sighting(self, sighting):
        if sighting.photo and sighting.missing_person.recent_photo:
            try:
                result = DeepFace.verify(
                    sighting.photo.path,
                    sighting.missing_person.recent_photo.path,
                    model_name='VGG-Face'
                )
                sighting.facial_match_confidence = 1 - result.get('distance', 1)  # Convert distance to confidence
                sighting.confidence_level = 'HIGH' if result.get('verified') else 'MEDIUM'
                sighting.ml_analysis_results = result
                sighting.save()
            except Exception as e:
                print(f"Facial recognition error: {str(e)}")

    def update_missing_person_status(self, sighting):
        if sighting.verification_status == 'VERIFIED' and sighting.confidence_level == 'HIGH':
            sighting.missing_person.status = 'FOUND'
            sighting.missing_person.last_known_latitude = sighting.latitude
            sighting.missing_person.last_known_longitude = sighting.longitude
            sighting.missing_person.save()

    def notify_relevant_parties(self, sighting):
        if sighting.is_notified:
            return

        recipients = [
            sighting.reporter.email,
            sighting.missing_person.emergency_contact_phone  # Assuming SMS integration
        ]
        if sighting.missing_person.assigned_officer:
            recipients.append(sighting.missing_person.assigned_officer.email)
        if sighting.missing_person.assigned_ngo:
            recipients.append(sighting.missing_person.assigned_ngo.email)

        message = (
            f"Sighting Update for {sighting.missing_person.name}:\n"
            f"Location: {sighting.location}\n"
            f"Status: {sighting.verification_status}\n"
            f"Details: {sighting.description}"
        )
        send_mail(
            'Sighting Update - Reunite',
            message,
            settings.DEFAULT_FROM_EMAIL,
            recipients,
            fail_silently=True
        )
        sighting.is_notified = True
        sighting.save()