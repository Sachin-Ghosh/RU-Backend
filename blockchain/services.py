from dataclasses import dataclass
from datetime import datetime
from .models import Block
import hashlib
import json

@dataclass
class Block:
    data: dict
    timestamp: str
    previous_hash: str
    hash: str

class BlockchainService:
    @staticmethod
    def add_block(data: dict, data_type: str = None) -> Block:
        """Add a new block to the blockchain"""
        try:
            # Create block data
            block_data = {
                'data': data,
                'data_type': data_type,
                'timestamp': datetime.now().isoformat()
            }
            
            # Create block hash
            block_hash = hashlib.sha256(
                json.dumps(block_data, sort_keys=True).encode()
            ).hexdigest()
            
            # Create block
            block = Block(
                data=data,
                timestamp=block_data['timestamp'],
                previous_hash="0",  # Simplified for example
                hash=block_hash
            )
            
            return block
            
        except Exception as e:
            print(f"Error adding block to blockchain: {str(e)}")
            return None

    @staticmethod
    def _hash_biometric_data(data):
        """Hash sensitive biometric data before storing"""
        if 'fingerprint_features' in data:
            data['fingerprint_features'] = hashlib.sha256(
                str(data['fingerprint_features']).encode()
            ).hexdigest()
        if 'facial_features' in data:
            data['facial_features'] = hashlib.sha256(
                str(data['facial_features']).encode()
            ).hexdigest()
        return data

    @staticmethod
    def verify_chain():
        blocks = Block.objects.all().order_by('timestamp')
        for i in range(1, len(blocks)):
            current_block = blocks[i]
            previous_block = blocks[i-1]
            
            if current_block.hash != current_block.calculate_hash():
                return False
            if current_block.previous_hash != previous_block.hash:
                return False
        return True