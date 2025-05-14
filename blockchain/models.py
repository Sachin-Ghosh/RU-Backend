# from django.db import models

from django.db import models
import hashlib
import json
from datetime import datetime

class Block(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    previous_hash = models.CharField(max_length=64)
    hash = models.CharField(max_length=64)
    data = models.JSONField()
    nonce = models.IntegerField(default=0)

    def calculate_hash(self):
        block_data = {
            'timestamp': self.timestamp.isoformat(),
            'previous_hash': self.previous_hash,
            'data': self.data,
            'nonce': self.nonce
        }
        block_string = json.dumps(block_data, sort_keys=True)
        return hashlib.sha256(block_string.encode()).hexdigest()

    def mine_block(self, difficulty=2):
        target = '0' * difficulty
        while self.hash[:difficulty] != target:
            self.nonce += 1
            self.hash = self.calculate_hash()
        return self.hash

    class Meta:
        ordering = ['-timestamp'] 