from deepface import DeepFace
from django.core.mail import send_mail
from django.conf import settings
from accounts.models import User
from django.utils import timezone
import uuid


from .models import Sighting
from missing_persons.models import MissingPerson

class SightingService:
    def process_sighting(self, sighting):
        if sighting.photo:
            matches = self.check_against_missing_persons(sighting)
            if matches:
                sighting.verification_status = 'VERIFIED'
                sighting.confidence_level = 'HIGH'
                sighting.facial_match_confidence = matches[0]['confidence']
                sighting.save()
                
                # Update matched missing person
                matched_person = matches[0]['person']
                matched_person.status = 'FOUND'
                matched_person.last_known_latitude = sighting.latitude
                matched_person.last_known_longitude = sighting.longitude
                matched_person.save()

        # Notify regardless of match
        notification_service = NotificationService()
        nearby = None
        if sighting.latitude and sighting.longitude:
            nearby = notification_service.find_nearby_entities(sighting.latitude, sighting.longitude)
        notification_service.notify_entities(sighting, nearby)

    def check_against_missing_persons(self, sighting):
        missing_persons = MissingPerson.objects.filter(recent_photo__isnull=False)
        matches = []
        
        for person in missing_persons:
            try:
                result = DeepFace.verify(
                    sighting.photo.path,
                    person.recent_photo.path,
                    model_name='VGG-Face'
                )
                if result.get('verified', False):
                    matches.append({
                        'person': person,
                        'confidence': 1 - result.get('distance', 1)
                    })
            except Exception as e:
                print(f"Error comparing with {person.name}: {str(e)}")
        
        return sorted(matches, key=lambda x: x['confidence'], reverse=True)

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

    def handle_unmatched_sighting(self, sighting):
        # Create potential missing person case
        if sighting.photo:
            # Store the photo as potential missing person
            potential_case = MissingPerson.objects.create(
                name=f"Unidentified Person - {sighting.created_at.strftime('%Y%m%d%H%M')}",
                status='REPORTED',
                recent_photo=sighting.photo,
                last_known_location=sighting.location,
                last_known_latitude=sighting.latitude,
                last_known_longitude=sighting.longitude,
                description=sighting.description,
                age_when_missing=0,  # Default value for unidentified persons
                gender='UNKNOWN',    # Default value
                height=0,           # Default value
                weight=0,           # Default value
                complexion='UNKNOWN', # Default value
                case_number=f"TEMP-{uuid.uuid4().hex[:8]}",
                last_seen_date=timezone.now(),
                reporter=sighting.reporter
            )
            sighting.missing_person = potential_case
            sighting.save()

class NotificationService:
    def __init__(self):
        self.sighting_service = SightingService()

    def find_nearby_entities(self, latitude, longitude, radius=50):  # radius in km
        nearby_ngos = User.objects.filter(
            role='NGO',
            latitude__isnull=False,
            longitude__isnull=False
        )
        nearby_police = User.objects.filter(
            role='LAW_ENFORCEMENT',  # Assuming 'LAW_ENFORCEMENT' is the role for police
            latitude__isnull=False,
            longitude__isnull=False
        )

        def calculate_distance(lat1, lon1, lat2, lon2):
            from math import radians, sin, cos, sqrt, asin
            lat1, lon1, lat2, lon2 = map(radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * asin(sqrt(a))
            r = 6371  # Radius of Earth in kilometers
            return c * r

        nearby = {'ngos': [], 'police': []}
        for ngo in nearby_ngos:
            distance = calculate_distance(latitude, longitude, ngo.latitude, ngo.longitude)
            if distance <= radius:
                nearby['ngos'].append({'user': ngo, 'distance': distance})

        for police in nearby_police:
            distance = calculate_distance(latitude, longitude, police.latitude, police.longitude)
            if distance <= radius:
                nearby['police'].append({'user': police, 'distance': distance})

        # If no nearby entities are found, return all NGOs and police
        if not nearby['ngos'] and not nearby['police']:
            nearby['ngos'] = [{'user': ngo, 'distance': None} for ngo in User.objects.filter(role='NGO')]
            nearby['police'] = [{'user': police, 'distance': None} for police in User.objects.filter(role='LAW_ENFORCEMENT')]

        return nearby

    def notify_entities(self, sighting, nearby_entities=None):
        if not nearby_entities and (sighting.latitude and sighting.longitude):
            nearby_entities = self.find_nearby_entities(sighting.latitude, sighting.longitude)

        # If still no entities (e.g., no coordinates provided), use all NGOs and police
        if not nearby_entities:
            nearby_entities = {
                'ngos': [{'user': ngo, 'distance': None} for ngo in User.objects.filter(role='NGO')],
                'police': [{'user': police, 'distance': None} for police in User.objects.filter(role='LAW_ENFORCEMENT')]
            }

        recipients = [entity['user'].email for entity in nearby_entities['ngos'] if entity['user'].email] + \
                     [entity['user'].email for entity in nearby_entities['police'] if entity['user'].email]

        if not recipients:
            print("No valid recipients found for notification.")
            return

        message = (
            f"New Sighting Reported:\n"
            f"Missing Person: {sighting.missing_person.name if sighting.missing_person else 'Unidentified'}\n"
            f"Location: {sighting.location}\n"
            f"Description: {sighting.description}\n"
            f"Confidence: {sighting.confidence_level_numeric}%\n"
            f"Contact Willing: {sighting.willing_to_contact}\n"
            f"Photo: {sighting.photo.url if sighting.photo else 'No photo provided'}\n"
            f"Timestamp: {sighting.timestamp}"
        )

        send_mail(
            'New Sighting Alert - Reunite',
            message,
            settings.DEFAULT_FROM_EMAIL,
            recipients,
            fail_silently=True
        )
        sighting.is_notified = True
        sighting.save()