"""
Crypto module: key derivation, encryption, and decryption for AES-GCM.

AES keys are wrapped with a passphrase-derived KEK (Argon2id) and stored
in ``aes.key``.
"""

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag
from argon2.low_level import hash_secret_raw, Type
from pathlib import Path
from typing import Tuple
import os

# Default key file paths
AES_KEY_PATH = Path("/home/bryce/school/497X/rf-encryption/keys/aes.key")

class Symmetric:
    """AES-GCM symmetric encryption with Argon2id-derived key wrapping."""
    AESGCM_DEK_LEN = 32
    AESGCM_SALT_LEN = 16
    AESGCM_NONCE_LEN = 12
    GCM_TAG_LEN = 16

    @staticmethod
    def _derive_kek(passphrase: str, salt: bytes) -> bytes:
        """Derive a key-encryption-key from the user's passphrase via Argon2id."""
        return hash_secret_raw(
            secret=passphrase.encode(),
            salt=salt,
            time_cost=3,
            memory_cost=65536,
            parallelism=2,
            hash_len=32,
            type=Type.ID
        )

    @staticmethod
    def load_or_generate_key(passphrase: str) -> bytes:
        """Load an existing AES DEK from *aes.key*, or generate and persist a new one."""
        if AES_KEY_PATH.is_file():
            blob = AES_KEY_PATH.read_bytes()
            salt = blob[:Symmetric.AESGCM_SALT_LEN]
            nonce = blob[Symmetric.AESGCM_SALT_LEN:
                         Symmetric.AESGCM_SALT_LEN + Symmetric.AESGCM_NONCE_LEN]
            ciphertext = blob[Symmetric.AESGCM_SALT_LEN + Symmetric.AESGCM_NONCE_LEN:]
            kek = Symmetric._derive_kek(passphrase, salt)
            try:
                return AESGCM(kek).decrypt(nonce, ciphertext, None)
            except InvalidTag:
                raise ValueError(
                    f"Wrong passphrase — could not decrypt '{AES_KEY_PATH}'. "
                    "Delete the key file to generate a new one."
                ) from None

        # Generate a fresh DEK and persist it wrapped by a passphrase-derived KEK
        dek = os.urandom(Symmetric.AESGCM_DEK_LEN)
        salt = os.urandom(Symmetric.AESGCM_SALT_LEN)
        nonce = os.urandom(Symmetric.AESGCM_NONCE_LEN)
        kek = Symmetric._derive_kek(passphrase, salt)
        ciphertext = AESGCM(kek).encrypt(nonce, dek, None)
        AES_KEY_PATH.write_bytes(salt + nonce + ciphertext)
        return dek

    @staticmethod
    def encrypt_aes(plaintext: bytes, dek: bytes) -> Tuple[bytes, bytes]:
        """Encrypt *plaintext* with AES-GCM. Returns ``(nonce, ciphertext)``."""
        nonce = os.urandom(Symmetric.AESGCM_NONCE_LEN)
        return nonce, AESGCM(dek).encrypt(nonce, plaintext, None)

    @staticmethod
    def decrypt_aes(ciphertext: bytes, dek: bytes, nonce: bytes) -> bytes:
        """Decrypt *ciphertext* with AES-GCM using the given *nonce*."""
        return AESGCM(dek).decrypt(nonce, ciphertext, None)

    @staticmethod
    def display_key(key: bytes):
        """Print the AES key as hex (for manual key-sharing)."""
        print("THIS IS YOUR SECRET AES KEY. "
              "ONLY SHARE THIS KEY WITH PEOPLE YOU WANT TO BE ABLE TO READ YOUR MESSAGES.")
        print(key.hex())

def main():
    """Interactive smoke test for AES-GCM encryption."""
    passphrase = input("Enter your passphrase: ")

    # --- AES round-trip ---
    print("SYMMETRIC ENCRYPTION TESTING:")
    key = Symmetric.load_or_generate_key(passphrase)
    plaintext_b = input("Enter plaintext for symmetric testing: ").encode("utf-8")
    nonce, ciphertext = Symmetric.encrypt_aes(plaintext_b, key)
    print(f"AES ciphertext: {ciphertext.hex()}")
    print(f"Decrypted: {Symmetric.decrypt_aes(ciphertext, key, nonce).decode('utf-8')}")

    # --- Key display ---
    print("KEY DISPLAY TESTING")
    Symmetric.display_key(key)


if __name__ == "__main__":
    main()