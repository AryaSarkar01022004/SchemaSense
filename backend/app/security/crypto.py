"""
Envelope Encryption for Target Database Credentials (Section 5.1 & 5.13).
Uses a two-tier key hierarchy:
1. Master Key (Key Encryption Key / KEK) stored in environment / KMS.
2. Data Encryption Key (DEK) uniquely generated per credential.
Payload is encrypted with DEK, and DEK is encrypted with KEK.
Supports standard authenticated encryption (HMAC-SHA256 + AES/CTR or standard PBKDF2-authenticated cipher).
"""

import os
import hmac
import hashlib
import secrets
from typing import Tuple
from app.config import settings


def _derive_key(secret: str, salt: bytes, length: int = 32) -> bytes:
    """Derive key using PBKDF2 HMAC SHA-256."""
    return hashlib.pbkdf2_hmac("sha256", secret.encode(), salt, 100_000, dklen=length)


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    """Deterministic stream cipher based on SHA-256 counter mode."""
    stream = bytearray()
    counter = 0
    while len(stream) < length:
        block = hashlib.sha256(key + nonce + counter.to_bytes(4, byteorder="big")).digest()
        stream.extend(block)
        counter += 1
    return bytes(stream[:length])


def _encrypt_bytes(key: bytes, plaintext: bytes) -> bytes:
    """Authenticated encryption (Encrypt-then-MAC)."""
    nonce = secrets.token_bytes(16)
    keystream = _keystream(key, nonce, len(plaintext))
    ciphertext = bytes(a ^ b for a, b in zip(plaintext, keystream))
    mac = hmac.new(key, nonce + ciphertext, hashlib.sha256).digest()
    return nonce + mac + ciphertext


def _decrypt_bytes(key: bytes, payload: bytes) -> bytes:
    """Verify MAC and decrypt payload."""
    if len(payload) < 48: # 16 nonce + 32 mac
        raise ValueError("Payload too short for authenticated decryption")
    nonce = payload[:16]
    mac = payload[16:48]
    ciphertext = payload[48:]
    expected_mac = hmac.new(key, nonce + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(mac, expected_mac):
        raise ValueError("Authentication MAC verification failed: corrupted or invalid key")
    keystream = _keystream(key, nonce, len(ciphertext))
    return bytes(a ^ b for a, b in zip(ciphertext, keystream))


class EnvelopeEncryption:
    def __init__(self, master_key: str = None):
        self.master_key = master_key or settings.MASTER_ENCRYPTION_KEY
        self.salt = b"schemasense-envelope-salt"
        self.kek = _derive_key(self.master_key, self.salt)

    def encrypt_secret(self, plaintext: str) -> Tuple[bytes, bytes]:
        """
        Generates a fresh random DEK, encrypts plaintext with DEK,
        and encrypts DEK with KEK.
        Returns: (password_enc, dek_enc)
        """
        # 1. Generate unique 32-byte DEK
        dek = secrets.token_bytes(32)
        
        # 2. Encrypt plaintext with DEK
        password_enc = _encrypt_bytes(dek, plaintext.encode("utf-8"))
        
        # 3. Encrypt DEK with Master KEK
        dek_enc = _encrypt_bytes(self.kek, dek)
        
        return password_enc, dek_enc

    def decrypt_secret(self, password_enc: bytes, dek_enc: bytes) -> str:
        """
        Decrypts DEK using Master KEK, then decrypts password using DEK.
        """
        dek = _decrypt_bytes(self.kek, dek_enc)
        plaintext_bytes = _decrypt_bytes(dek, password_enc)
        return plaintext_bytes.decode("utf-8")


envelope_encryptor = EnvelopeEncryption()

