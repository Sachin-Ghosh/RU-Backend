from celery import shared_task
import cv2
import numpy as np
from deepface import DeepFace
from datetime import timedelta
from .models import SurveillanceFootage
from sightings.models import Sighting
from missing_persons.models import MissingPerson
import tempfile
import os

@shared_task
def process_surveillance_footage(footage_id, missing_person_id=None):
    """Process surveillance footage for face detection and matching"""
    footage = SurveillanceFootage.objects.get(id=footage_id)
    
    try:
        # Open video file
        cap = cv2.VideoCapture(footage.file.path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        frame_interval = 30
        matches = []
        
        for frame_no in range(0, frame_count, frame_interval):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
            ret, frame = cap.read()
            if not ret:
                continue
                
            # Save frame temporarily
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
                cv2.imwrite(temp_file.name, frame)
                
                try:
                    # Detect faces in the frame
                    faces = DeepFace.extract_faces(
                        temp_file.name,
                        detector_backend='retinaface'
                    )
                    
                    # If searching for specific person
                    if missing_person_id:
                        missing_person = MissingPerson.objects.get(id=missing_person_id)
                        
                        for face in faces:
                            try:
                                result = DeepFace.verify(
                                    temp_file.name,
                                    missing_person.recent_photo.path,
                                    model_name='VGG-Face',
                                    distance_metric='cosine'
                                )
                                
                                if result.get('verified', False):
                                    timestamp = footage.timestamp + timedelta(
                                        seconds=frame_no/fps
                                    )
                                    matches.append({
                                        'frame_no': frame_no,
                                        'timestamp': timestamp,
                                        'confidence': result.get('distance', 0)
                                    })
                            except Exception as e:
                                print(f"Face matching error: {str(e)}")
                                continue
                    
                finally:
                    os.unlink(temp_file.name)
        
        cap.release()
        
        # Create sightings for matches
        if matches and missing_person_id:
            for match in matches:
                Sighting.objects.create(
                    missing_person_id=missing_person_id,
                    location=footage.location_name,
                    latitude=footage.latitude,
                    longitude=footage.longitude,
                    timestamp=match['timestamp'],
                    confidence_level='HIGH' if match['confidence'] > 0.8 else 'MEDIUM',
                    description=f"Detected in surveillance footage",
                    verification_status='PENDING',
                    facial_match_confidence=match['confidence'],
                    ml_analysis_results={
                        'frame_number': match['frame_no'],
                        'footage_id': footage.id,
                        'detection_type': 'automated'
                    }
                )
        
        footage.processed = True
        footage.save()
        
        return {
            'footage_id': footage.id,
            'matches_found': len(matches),
            'match_details': matches
        }
        
    except Exception as e:
        print(f"Processing error: {str(e)}")
        return None 