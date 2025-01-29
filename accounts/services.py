import os
import tempfile
from django.core.files.storage import default_storage
from accounts.models import AadhaarProfile
from authentication.services import BiometricHashingService
from blockchain.services import BlockchainService
import hashlib
from datetime import datetime
from django.utils import timezone

class RegistrationService:
    @staticmethod
    def validate_user_data(user_data, aadhaar_data):
        """Validate user provided data against Aadhaar data"""
        try:
            # Convert names to lowercase and split into parts
            user_name_parts = f"{user_data['first_name']} {user_data['last_name']}".lower().split()
            aadhaar_name_parts = aadhaar_data['name'].lower().split()
            
            # Extract first and last name from both
            user_first_name = user_name_parts[0]
            user_last_name = user_name_parts[-1]
            aadhaar_first_name = aadhaar_name_parts[0]
            aadhaar_last_name = aadhaar_name_parts[-1]
            
            # Check if first and last names match
            if user_first_name == aadhaar_first_name and user_last_name == aadhaar_last_name:
                return True
                
            # Check if user's name parts are contained in Aadhaar name
            user_name_set = set(user_name_parts)
            aadhaar_name_set = set(aadhaar_name_parts)
            if user_name_set.issubset(aadhaar_name_set):
                return True
                
            # Check if at least first name and last name partially match
            first_name_match = user_first_name in aadhaar_first_name or aadhaar_first_name in user_first_name
            last_name_match = user_last_name in aadhaar_last_name or aadhaar_last_name in user_last_name
            if first_name_match and last_name_match:
                return True
            
            # If none of the above conditions match, raise error
            raise ValueError(
                f"Name mismatch: User provided '{' '.join(user_name_parts)}' "
                f"but Aadhaar shows '{' '.join(aadhaar_name_parts)}'. "
                "Please provide name exactly as in Aadhaar card."
            )
            
        except Exception as e:
            print(f"Error in name validation: {str(e)}")
            raise ValueError(str(e))

    @staticmethod
    def process_registration(user, aadhaar_image, profile_picture, fingerprint=None):
        """Process user registration with biometric data"""
        temp_files = []
        temp_file_handles = []
        
        try:
            biometric_service = BiometricHashingService()
            
            # Save files temporarily
            temp_aadhaar = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            temp_profile_picture = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            temp_file_handles.extend([temp_aadhaar, temp_profile_picture])
            temp_files.extend([temp_aadhaar.name, temp_profile_picture.name])
            
            # Save uploaded files
            for chunk in aadhaar_image.chunks():
                temp_aadhaar.write(chunk)
            temp_aadhaar.flush()
                
            for chunk in profile_picture.chunks():
                temp_profile_picture.write(chunk)
            temp_profile_picture.flush()
            
            # Close file handles
            for handle in temp_file_handles:
                handle.close()
            
            # Extract and validate Aadhaar data
            aadhaar_data = biometric_service.extract_aadhaar_data(temp_aadhaar.name)
            
            # Print debug information
            print("Validating names:")
            print(f"User provided: {user.first_name} {user.last_name}")
            print(f"Aadhaar shows: {aadhaar_data['name']}")
            
            # Validate user data against Aadhaar data
            user_data = {
                'first_name': user.first_name,
                'last_name': user.last_name,
            }
            RegistrationService.validate_user_data(user_data, aadhaar_data)
            
            # Create facial signature
            facial_sig = biometric_service.create_facial_signature(temp_profile_picture.name)
            if not facial_sig:
                raise ValueError("Could not create facial signature")
            
            # Process fingerprint if provided
            fingerprint_hash = None
            if fingerprint:
                temp_fingerprint = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
                temp_files.append(temp_fingerprint.name)
                for chunk in fingerprint.chunks():
                    temp_fingerprint.write(chunk)
                temp_fingerprint.flush()
                temp_fingerprint.close()
                fingerprint_hash = biometric_service.hash_fingerprint(temp_fingerprint.name)
            
            # Create blockchain record with current timestamp
            current_time = datetime.now().isoformat()
            blockchain_data = {
                'user_id': user.id,
                'aadhaar_hash': aadhaar_data['document_hash'],
                'facial_signature': facial_sig,
                'fingerprint_hash': fingerprint_hash,
                'timestamp': current_time
            }
            
            try:
                block = BlockchainService.add_block(blockchain_data, data_type='registration')
                blockchain_reference = block.hash if block else None
            except Exception as e:
                print(f"Blockchain error: {str(e)}")
                blockchain_reference = None
            
            # Create AadhaarProfile
            aadhaar_profile = AadhaarProfile.objects.create(
                user=user,
                aadhaar_number_hash=hashlib.sha256(
                    aadhaar_data['aadhaar_number'].encode()
                ).hexdigest(),
                name_in_aadhaar=aadhaar_data['name'],
                dob=aadhaar_data['dob'],
                gender=aadhaar_data['gender'],
                document_hash=aadhaar_data['document_hash'],
                facial_signature=facial_sig,
                fingerprint_hash=fingerprint_hash,
                blockchain_reference=blockchain_reference
            )
            
            return aadhaar_profile
            
        except Exception as e:
            print(f"Error in registration process: {str(e)}")
            raise
            
        finally:
            # Clean up temporary files
            for temp_file in temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.unlink(temp_file)
                except Exception as e:
                    print(f"Error deleting temporary file {temp_file}: {str(e)}") 