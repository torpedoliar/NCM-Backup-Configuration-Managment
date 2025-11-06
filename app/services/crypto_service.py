"""Cryptography service for credential encryption"""
import json
import logging
from typing import Dict
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os
from pathlib import Path
from app.config.paths import get_base_dir

logger = logging.getLogger(__name__)


class CryptoService:
    """Handles encryption/decryption of credentials"""
    
    def __init__(self, passphrase: str):
        """Initialize with master passphrase"""
        self.salt = self._get_or_create_salt()
        self.cipher = self._derive_cipher(passphrase)
        # Validate passphrase by testing encryption/decryption
        self._validate_passphrase()
    
    def _get_or_create_salt(self) -> bytes:
        """Get existing salt or create new one"""
        base_dir = get_base_dir()
        salt_file = base_dir / "data" / "master.key"
        if salt_file.exists():
            with open(salt_file, 'rb') as f:
                return f.read(16)  # Read only first 16 bytes (salt)
        else:
            salt = os.urandom(16)
            (base_dir / "data").mkdir(exist_ok=True)
            with open(salt_file, 'wb') as f:
                f.write(salt)
            return salt
    
    def _derive_cipher(self, passphrase: str) -> Fernet:
        """Derive encryption key from passphrase"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))
        return Fernet(key)
    
    def _validate_passphrase(self):
        """Validate passphrase by testing encryption/decryption with test token"""
        base_dir = get_base_dir()
        salt_file = base_dir / "data" / "master.key"
        test_token = b"VALID_PASSPHRASE_TEST_TOKEN"
        
        # If salt file exists and has validation token
        if salt_file.exists():
            with open(salt_file, 'rb') as f:
                file_content = f.read()
                
            # If file is larger than 16 bytes (salt + encrypted token)
            if len(file_content) > 16:
                salt = file_content[:16]
                encrypted_token = file_content[16:]
                
                # Try to decrypt the token
                try:
                    decrypted = self.cipher.decrypt(encrypted_token)
                    if decrypted != test_token:
                        raise ValueError("Invalid master passphrase")
                    logger.info("Master passphrase validated successfully")
                except Exception as e:
                    logger.error(f"Passphrase validation failed: {e}")
                    raise ValueError(
                        "Invalid master passphrase!\n\n"
                        "The passphrase you entered does not match the one used to encrypt the credentials.\n\n"
                        "Please enter the correct passphrase, or delete 'data/master.key' and 'data/app.db' \n"
                        "to start fresh (WARNING: This will delete all saved data)."
                    )
            else:
                # First time - create validation token
                encrypted_token = self.cipher.encrypt(test_token)
                with open(salt_file, 'wb') as f:
                    f.write(self.salt)
                    f.write(encrypted_token)
                logger.info("Master passphrase validation token created")
    
    def encrypt_credential(self, username: str, password: str, enable_password: str = "") -> bytes:
        """Encrypt credential data"""
        data = {
            "username": username,
            "password": password,
            "enable_password": enable_password
        }
        json_data = json.dumps(data).encode()
        encrypted = self.cipher.encrypt(json_data)
        logger.debug("Credential encrypted")
        return encrypted
    
    def decrypt_credential(self, enc_blob: bytes) -> Dict[str, str]:
        """Decrypt credential data"""
        try:
            decrypted = self.cipher.decrypt(enc_blob)
            data = json.loads(decrypted.decode())
            logger.debug("Credential decrypted")
            return data
        except Exception as e:
            logger.error(f"Failed to decrypt credential: {e}")
            raise ValueError("Invalid credentials or wrong passphrase")
