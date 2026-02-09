"""
Credential Manager
Handles encrypted credential storage and retrieval
"""

import logging
from cryptography.fernet import Fernet
import json
import os
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class CredentialManager:
    """Manages encrypted credentials"""

    def __init__(self, key_file='/app/.encryption_key', credentials_file='/app/.iracing_credentials'):
        self.key_file = key_file
        self.credentials_file = credentials_file
        # Enforce restrictive permissions on credential files at init
        self._enforce_permissions()

    def _enforce_permissions(self):
        """Ensure credential files have restrictive permissions (owner read/write only)."""
        for path in (self.key_file, self.credentials_file):
            if os.path.exists(path):
                try:
                    os.chmod(path, 0o600)
                except (OSError, PermissionError):
                    # May fail on mounted volumes (e.g., Docker) — this is expected
                    logger.debug("Could not set chmod 600 on %s (mounted volume?)", path)

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
            # Enforce permissions before reading
            self._enforce_permissions()

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
                logger.error("Encrypted credentials missing email or password")
                return None

        except Exception as e:
            logger.error("Error decrypting credentials: %s", e)
            return None

    def remove_credentials(self):
        """Remove encrypted credentials and key (cleanup)"""
        try:
            if os.path.exists(self.credentials_file):
                os.remove(self.credentials_file)
                logger.info("Removed %s", self.credentials_file)

            if os.path.exists(self.key_file):
                os.remove(self.key_file)
                logger.info("Removed %s", self.key_file)

            return True
        except Exception as e:
            logger.error("Error removing credentials: %s", e)
            return False
