"""
Credential Manager
Handles encrypted credential storage and retrieval
"""

from cryptography.fernet import Fernet
import json
import os
from typing import Optional, Tuple


class CredentialManager:
    """Manages encrypted credentials"""

    def __init__(self, key_file='/app/.encryption_key', credentials_file='/app/.iracing_credentials'):
        self.key_file = key_file
        self.credentials_file = credentials_file

    def credentials_exist(self) -> bool:
        """Check if encrypted credentials exist"""
        return os.path.exists(self.key_file) and os.path.exists(self.credentials_file)

    def get_iracing_credentials(self) -> Optional[dict]:
        """
        Retrieve and decrypt iRacing credentials.

        Returns:
            Dict with keys: email, password, client_id, client_secret
            Or None if not available
        """
        if not self.credentials_exist():
            return None

        try:
            # Read encryption key
            with open(self.key_file, 'rb') as f:
                key = f.read()

            # Read encrypted credentials
            with open(self.credentials_file, 'rb') as f:
                encrypted_data = f.read()

            # Decrypt
            f = Fernet(key)
            decrypted = f.decrypt(encrypted_data)
            credentials = json.loads(decrypted.decode())

            email = credentials.get('email')
            password = credentials.get('password')
            client_id = credentials.get('client_id')
            client_secret = credentials.get('client_secret')

            if email and password:
                return {
                    'email': email,
                    'password': password,
                    'client_id': client_id,
                    'client_secret': client_secret
                }
            else:
                print("❌ Error: Encrypted credentials missing email or password")
                return None

        except Exception as e:
            print(f"❌ Error decrypting credentials: {e}")
            return None

    def remove_credentials(self):
        """Remove encrypted credentials and key (cleanup)"""
        try:
            if os.path.exists(self.credentials_file):
                os.remove(self.credentials_file)
                print(f"✓ Removed {self.credentials_file}")

            if os.path.exists(self.key_file):
                os.remove(self.key_file)
                print(f"✓ Removed {self.key_file}")

            return True
        except Exception as e:
            print(f"❌ Error removing credentials: {e}")
            return False
