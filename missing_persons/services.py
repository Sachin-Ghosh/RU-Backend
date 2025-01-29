import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
import cv2
import pickle
import os
from django.conf import settings

class BiometricService:
    def __init__(self):
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        self.fingerprint_model_path = os.path.join(settings.BASE_DIR, 'ml_models', 'fingerprint_model.pkl')
        self.face_model_path = os.path.join(settings.BASE_DIR, 'ml_models', 'face_model.pkl')
        
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

    def extract_facial_features(self, image_path):
        # Read and preprocess image
        img = cv2.imread(image_path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Detect faces
        faces = self.face_cascade.detectMultiScale(gray, 1.1, 4)
        
        if len(faces) == 0:
            return np.zeros(128)
        
        # Get the first face
        (x, y, w, h) = faces[0]
        face = gray[y:y+h, x:x+w]
        
        # Extract features using SIFT
        sift = cv2.SIFT_create()
        keypoints, descriptors = sift.detectAndCompute(face, None)
        
        if descriptors is None:
            return np.zeros(128)
        
        return np.mean(descriptors, axis=0)

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
                    features = self.extract_facial_features(face_path)
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
        features = self.extract_facial_features(face_path)
        prediction = self.face_model.predict_proba([features])[0]
        confidence = np.max(prediction)
        predicted_label = self.label_encoder.inverse_transform([np.argmax(prediction)])[0]
        return predicted_label, confidence 