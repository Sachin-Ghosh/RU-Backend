import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
import cv2
import pickle
import os
from django.conf import settings
from django.db.models import Q
from accounts.models import FamilyMember, User, AadhaarProfile
from .models import MissingPerson, MissingPersonDocument
from sklearn.metrics.pairwise import cosine_similarity
import hashlib
import tempfile
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import io

class BiometricService:
    def __init__(self):
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        self.fingerprint_model_path = os.path.join(settings.BASE_DIR, 'ml_models', 'fingerprint_model.pkl')
        self.face_model_path = os.path.join(settings.BASE_DIR, 'ml_models', 'face_model.pkl')
        self.sift = cv2.SIFT_create()
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(self.fingerprint_model_path), exist_ok=True)
        
        # Load or initialize models
        self.fingerprint_model = self.load_model(self.fingerprint_model_path)
        self.face_model = self.load_model(self.face_model_path)
        self.label_encoder = LabelEncoder()

    def load_model(self, path):
        if os.path.exists(path):
            with open(path, 'rb') as f:
                return pickle.load(f)
        return RandomForestClassifier(n_estimators=100)

    def save_model(self, model, path):
        with open(path, 'wb') as f:
            pickle.dump(model, f)

    def extract_fingerprint_features(self, image_path):
        # Read and preprocess fingerprint image
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        img = cv2.resize(img, (128, 128))
        
        # Extract features (using SIFT for better feature detection)
        sift = cv2.SIFT_create()
        keypoints, descriptors = sift.detectAndCompute(img, None)
        
        if descriptors is None:
            return np.zeros(128)  # Return zero vector if no features found
        
        # Return mean of descriptors as feature vector
        return np.mean(descriptors, axis=0)

    def extract_face_features(self, image_path):
        """Extract facial features using SIFT"""
        try:
            # Read image
            img = cv2.imread(image_path)
            if img is None:
                return None
            
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Detect faces
            faces = self.face_cascade.detectMultiScale(gray, 1.1, 4)
            
            if len(faces) == 0:
                return None
                
            # Get the largest face
            (x, y, w, h) = max(faces, key=lambda f: f[2] * f[3])
            face = gray[y:y+h, x:x+w]
            
            # Extract SIFT features
            keypoints, descriptors = self.sift.detectAndCompute(face, None)
            
            if descriptors is None:
                return None
                
            # Return mean of descriptors as feature vector
            return np.mean(descriptors, axis=0)
            
        except Exception as e:
            print(f"Error extracting face features: {str(e)}")
            return None

    def compare_faces(self, features1, features2):
        """Compare two face feature vectors"""
        if features1 is None or features2 is None:
            return 0.0
        return cosine_similarity([features1], [features2])[0][0]

    def train_models(self, dataset_path):
        fingerprint_features = []
        face_features = []
        labels = []
        
        # Process dataset
        for person_id in os.listdir(dataset_path):
            person_path = os.path.join(dataset_path, person_id)
            if os.path.isdir(person_path):
                # Process fingerprints
                fingerprint_path = os.path.join(person_path, 'fingerprint.jpg')
                if os.path.exists(fingerprint_path):
                    features = self.extract_fingerprint_features(fingerprint_path)
                    fingerprint_features.append(features)
                    labels.append(person_id)
                
                # Process face images
                face_path = os.path.join(person_path, 'face.jpg')
                if os.path.exists(face_path):
                    features = self.extract_face_features(face_path)
                    face_features.append(features)
        
        # Train models
        if fingerprint_features:
            encoded_labels = self.label_encoder.fit_transform(labels)
            self.fingerprint_model.fit(fingerprint_features, encoded_labels)
            self.save_model(self.fingerprint_model, self.fingerprint_model_path)
        
        if face_features:
            self.face_model.fit(face_features, encoded_labels)
            self.save_model(self.face_model, self.face_model_path)

    def match_fingerprint(self, fingerprint_path):
        features = self.extract_fingerprint_features(fingerprint_path)
        prediction = self.fingerprint_model.predict_proba([features])[0]
        confidence = np.max(prediction)
        predicted_label = self.label_encoder.inverse_transform([np.argmax(prediction)])[0]
        return predicted_label, confidence

    def match_face(self, face_path):
        features = self.extract_face_features(face_path)
        prediction = self.face_model.predict_proba([features])[0]
        confidence = np.max(prediction)
        predicted_label = self.label_encoder.inverse_transform([np.argmax(prediction)])[0]
        return predicted_label, confidence

    def extract_features_from_file(self, file):
        """Extract features from an uploaded file"""
        try:
            # Read file content
            content = file.read()
            
            # Convert to numpy array
            nparr = np.frombuffer(content, np.uint8)
            
            # Decode image
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                return None

            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Detect faces
            faces = self.face_cascade.detectMultiScale(gray, 1.1, 4)
            
            if len(faces) == 0:
                return None
                
            # Get the largest face
            (x, y, w, h) = max(faces, key=lambda f: f[2] * f[3])
            face = gray[y:y+h, x:x+w]
            
            # Extract SIFT features
            keypoints, descriptors = self.sift.detectAndCompute(face, None)
            
            if descriptors is None:
                return None
                
            # Reset file pointer
            file.seek(0)
            
            # Return mean of descriptors as feature vector
            return np.mean(descriptors, axis=0)
            
        except Exception as e:
            print(f"Error extracting features: {str(e)}")
            return None

    def compare_features(self, features1, features2):
        """Compare two feature vectors"""
        if features1 is None or features2 is None:
            return 0.0
        return cosine_similarity([features1], [features2])[0][0]

class MissingPersonService:
    def __init__(self):
        self.biometric_service = BiometricService()

    @staticmethod
    def search_by_aadhaar(aadhaar_number):
        """Search for missing person by Aadhaar number"""
        aadhaar_hash = hashlib.sha256(aadhaar_number.encode()).hexdigest()
        return MissingPerson.objects.filter(
            Q(aadhaar_number_hash=aadhaar_hash) |
            Q(registered_user__aadhaar_profile__aadhaar_number_hash=aadhaar_hash)
        )

    @staticmethod
    def search_by_name(name):
        """Search for missing person by name"""
        name_parts = name.lower().split()
        return MissingPerson.objects.filter(
            Q(name__icontains=name) |
            Q(registered_user__first_name__in=name_parts) |
            Q(registered_user__last_name__in=name_parts)
        )

    @staticmethod
    def match_faces(photo_path, threshold=0.6):
        """Match face against database of missing persons"""
        biometric_service = BiometricService()
        query_features = biometric_service.extract_face_features(photo_path)
        
        matches = []
        for person in MissingPerson.objects.filter(status='MISSING'):
            if person.facial_encoding:
                similarity = biometric_service.compare_faces(
                    query_features,
                    np.array(person.facial_encoding)
                )
                
                if similarity > threshold:
                    matches.append({
                        'person': person,
                        'confidence': similarity
                    })
        
        return sorted(matches, key=lambda x: x['confidence'], reverse=True)

    @staticmethod
    def update_location(missing_person, latitude, longitude, timestamp):
        """Update last known location of missing person"""
        location_data = {
            'latitude': latitude,
            'longitude': longitude,
            'timestamp': timestamp.isoformat()
        }
        
        if not missing_person.last_known_location:
            missing_person.last_known_location = {'history': []}
        
        missing_person.last_known_location['history'].append(location_data)
        missing_person.last_known_location['current'] = location_data
        missing_person.save()

    @staticmethod
    def get_family_member_details(family_member_id):
        """Get details of a family member for pre-filling"""
        try:
            member = FamilyMember.objects.get(id=family_member_id)
            user = member.user
            aadhaar_profile = getattr(user, 'aadhaar_profile', None)
            
            return {
                'name': user.get_full_name(),
                'age': calculate_age(aadhaar_profile.dob) if aadhaar_profile else None,
                'gender': aadhaar_profile.gender if aadhaar_profile else None,
                'blood_group': user.blood_group if hasattr(user, 'blood_group') else None,
                'photo': user.profile_picture.url if user.profile_picture else None,
                'aadhaar_number_hash': aadhaar_profile.aadhaar_number_hash if aadhaar_profile else None,
            }
        except FamilyMember.DoesNotExist:
            return None

    def handle_document_uploads(self, documents_data, document_files, missing_person, user):
        """Handle document uploads and verification"""
        for idx, doc_data in enumerate(documents_data):
            try:
                doc_file = document_files.get(idx)
                if not doc_file:
                    continue

                # Create document record
                document = MissingPersonDocument.objects.create(
                    missing_person=missing_person,
                    document_type=doc_data['document_type'],
                    document=doc_file,
                    description=doc_data.get('description', ''),
                    uploaded_by=user
                )

                # If document is Aadhaar, verify against database
                if doc_data['document_type'] == 'ID_PROOF' and 'Aadhaar' in doc_data.get('description', ''):
                    self.verify_aadhaar_document(document, missing_person)

            except Exception as e:
                print(f"Error uploading document {idx}: {str(e)}")

    
    def process_recent_photo(self, missing_person):
        """Process recent photo for facial recognition"""
        try:
            if missing_person.recent_photo:
                # Extract features from recent photo
                recent_features = self.biometric_service.extract_face_features(
                    missing_person.recent_photo.path
                )
                
                if recent_features is not None:
                    missing_person.facial_encoding = recent_features.tolist()
                    
                    # Match against user profile photos
                    best_match = None
                    highest_confidence = 0.0

                    for user in User.objects.filter(profile_picture__isnull=False):
                        if user.profile_picture:
                            profile_features = self.biometric_service.extract_face_features(
                                user.profile_picture.path
                            )
                            
                            if profile_features is None:
                                continue

                            confidence = self.biometric_service.compare_faces(
                                recent_features, 
                                profile_features
                            )
                            
                            if confidence > highest_confidence:
                                highest_confidence = confidence
                                best_match = user

                    # Update missing person record if match found
                    if best_match and highest_confidence > 0.6:
                        missing_person.is_registered_user = True
                        missing_person.registered_user = best_match
                        missing_person.facial_match_confidence = highest_confidence
                        missing_person.save()

        except Exception as e:
            print(f"Error processing recent photo: {str(e)}")

    def process_photos(self, missing_person, recent_photo=None, additional_photos=None):
        """Process photos for facial recognition"""
        try:
            if recent_photo:
                # Extract features from recent photo
                features = self.biometric_service.extract_features_from_file(recent_photo)
                if features is not None:
                    missing_person.facial_encoding = features.tolist()
                    missing_person.save()

                    # Match against profile photos
                    self.match_against_profiles(missing_person, features)

            # Save additional photos
            if additional_photos:
                for photo in additional_photos:
                    path = default_storage.save(
                        f'missing_persons/additional_photos/{missing_person.id}_{photo.name}',
                        ContentFile(photo.read())
                    )
                    missing_person.additional_photos.append(path)
                missing_person.save()

        except Exception as e:
            print(f"Error processing photos: {str(e)}")

    def match_against_profiles(self, missing_person, features):
        """Match features against user profile photos"""
        try:
            from accounts.models import User
            best_match = None
            highest_confidence = 0.0

            for user in User.objects.filter(profile_picture__isnull=False):
                if user.profile_picture:
                    # Read profile picture
                    with user.profile_picture.open('rb') as f:
                        profile_features = self.biometric_service.extract_features_from_file(f)
                        
                        if profile_features is not None:
                            confidence = self.biometric_service.compare_features(
                                features, 
                                profile_features
                            )
                            
                            if confidence > highest_confidence:
                                highest_confidence = confidence
                                best_match = user

            if best_match and highest_confidence > 0.6:
                missing_person.is_registered_user = True
                missing_person.registered_user = best_match
                missing_person.facial_match_confidence = highest_confidence
                missing_person.save()

        except Exception as e:
            print(f"Error matching against profiles: {str(e)}")

    def process_documents(self, missing_person, documents_data):
        """Process and save documents"""
        try:
            for doc_data in documents_data:
                if doc_data:
                    document = MissingPersonDocument.objects.create(
                        missing_person=missing_person,
                        document_type=doc_data.get('document_type'),
                        description=doc_data.get('description', ''),
                        document=doc_data.get('document')
                    )

                    # If it's an Aadhaar document, try to match
                    if (doc_data.get('document_type') == 'ID_PROOF' and 
                        'Aadhaar' in doc_data.get('description', '')):
                        self.match_aadhaar_document(document)

        except Exception as e:
            print(f"Error processing documents: {str(e)}")

    def match_aadhaar_document(self, document):
        """Match Aadhaar document against database"""
        try:
            from accounts.models import AadhaarProfile
            
            with document.document.open('rb') as f:
                doc_features = self.biometric_service.extract_features_from_file(f)
                
                if doc_features is not None:
                    best_match = None
                    highest_confidence = 0.0

                    for profile in AadhaarProfile.objects.all():
                        if profile.aadhaar_image:
                            with profile.aadhaar_image.open('rb') as f:
                                profile_features = self.biometric_service.extract_features_from_file(f)
                                
                                if profile_features is not None:
                                    confidence = self.biometric_service.compare_features(
                                        doc_features,
                                        profile_features
                                    )
                                    
                                    if confidence > highest_confidence:
                                        highest_confidence = confidence
                                        best_match = profile

                    if best_match and highest_confidence > 0.6:
                        document.missing_person.is_registered_user = True
                        document.missing_person.registered_user = best_match.user
                        document.missing_person.aadhaar_number_hash = best_match.aadhaar_number_hash
                        document.missing_person.save()

        except Exception as e:
            print(f"Error matching Aadhaar document: {str(e)}") 