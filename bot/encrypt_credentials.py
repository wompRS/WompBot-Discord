#!/usr/bin/env python3
"""
Credential Encryption Utility
Encrypts iRacing credentials for secure storage
"""

from cryptography.fernet import Fernet
import json
import os
import sys

def generate_key():
    """Generate a new encryption key"""
    return Fernet.generate_key()

def encrypt_credentials(email, password, key):
    """Encrypt credentials using Fernet symmetric encryption"""
    f = Fernet(key)

    credentials = {
        'email': email,
        'password': password
    }

    # Convert to JSON and encrypt
    credentials_json = json.dumps(credentials).encode()
    encrypted = f.encrypt(credentials_json)

    return encrypted

def decrypt_credentials(encrypted_data, key):
    """Decrypt credentials"""
    f = Fernet(key)
    decrypted = f.decrypt(encrypted_data)
    return json.loads(decrypted.decode())

def main():
    print("=" * 60)
    print("iRacing Credential Encryption Utility")
    print("=" * 60)
    print()

    # Check if encryption key exists
    key_file = '/app/.encryption_key'
    credentials_file = '/app/.iracing_credentials'

    if os.path.exists(key_file):
        print(f"✓ Found existing encryption key at {key_file}")
        with open(key_file, 'rb') as f:
            key = f.read()
    else:
        print(f"✗ No encryption key found. Generating new key...")
        key = generate_key()
        with open(key_file, 'wb') as f:
            f.write(key)
        os.chmod(key_file, 0o600)  # Restrict to owner only
        print(f"✓ Generated and saved encryption key to {key_file}")
        print(f"  (File permissions set to 600 - owner read/write only)")

    print()
    print("Please enter your iRacing credentials:")
    print("(These will be encrypted and stored securely)")
    print()

    # Get credentials
    email = input("iRacing Email: ").strip()
    password = input("iRacing Password: ").strip()

    if not email or not password:
        print("\n❌ Error: Email and password cannot be empty")
        sys.exit(1)

    print()
    print("Encrypting credentials...")

    # Encrypt
    encrypted = encrypt_credentials(email, password, key)

    # Save encrypted credentials
    with open(credentials_file, 'wb') as f:
        f.write(encrypted)

    os.chmod(credentials_file, 0o600)  # Restrict to owner only

    print(f"✓ Encrypted credentials saved to {credentials_file}")
    print(f"  (File permissions set to 600 - owner read/write only)")
    print()

    # Verify by decrypting
    print("Verifying encryption...")
    with open(credentials_file, 'rb') as f:
        encrypted_data = f.read()

    decrypted = decrypt_credentials(encrypted_data, key)

    if decrypted['email'] == email:
        print("✓ Verification successful! Credentials encrypted correctly.")
        print()
        print("=" * 60)
        print("IMPORTANT NOTES:")
        print("=" * 60)
        print(f"1. Encryption key stored in: {key_file}")
        print(f"2. Encrypted credentials stored in: {credentials_file}")
        print(f"3. Both files have 600 permissions (owner read/write only)")
        print(f"4. DO NOT commit these files to git!")
        print(f"5. DO NOT share your encryption key!")
        print()
        print("✓ Setup complete! Restart the bot to use encrypted credentials.")
        print("=" * 60)
    else:
        print("❌ Verification failed! Something went wrong.")
        sys.exit(1)

if __name__ == "__main__":
    main()
