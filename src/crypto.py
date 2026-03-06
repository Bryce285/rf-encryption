"""
Crypto module: key derivation, encryption, and decryption for AES-GCM
and RSA-OAEP.

AES keys are wrapped with a passphrase-derived KEK (Argon2id) and stored
in ``aes.key``.  RSA private keys are stored PEM-encrypted in
``rsa_private.key``.
"""

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization

from pathlib import Path
from typing import Tuple

import os
from argon2.low_level import hash_secret_raw, Type

"""
For AES symmetric encryption
"""
class Symmetric:
    AESGCM_DEK_LEN = 32
    AESGCM_SALT_LEN = 16
    AESGCM_NONCE_LEN = 12
    GCM_TAG_LEN = 16

    """
    Checks if an AES key file exists and either loads the key from that file
    or generates a new key and writes it to a file.

    Parameters: the user's passphrase
    Returns: data encryption key on success, nothing on failure
    """
    @staticmethod
    def load_or_generate_key(passphrase: str) -> bytes:
        dek = b""
    
        if Path("aes.key").exists() and Path("aes.key").is_file():
            salt = b""
            nonce = b""
            ciphertext = b""

            try:
                with open("aes.key", "rb") as aes_key_file:
                    salt = aes_key_file.read(Symmetric.AESGCM_SALT_LEN)
                    nonce = aes_key_file.read(Symmetric.AESGCM_NONCE_LEN)
                    ciphertext = aes_key_file.read(Symmetric.GCM_TAG_LEN + Symmetric.AESGCM_DEK_LEN)
            except FileNotFoundError:
                print("aes.key file not found")
                return
            except OSError:
                print("Failed to read AES key from aes.key")
                return

            kek = hash_secret_raw(
                secret=passphrase.encode(),
                salt=salt,
                time_cost=3,
                memory_cost=65536,
                parallelism=2,
                hash_len=32,
                type=Type.ID
            )

            aesgcm = AESGCM(kek)
            dek = aesgcm.decrypt(nonce, ciphertext, None)

        else:
            dek = os.urandom(Symmetric.AESGCM_DEK_LEN)
            salt = os.urandom(Symmetric.AESGCM_SALT_LEN)
            kek = hash_secret_raw(
                secret=passphrase.encode(),
                salt=salt,
                time_cost=3,
                memory_cost=65536,
                parallelism=2,
                hash_len=32,
                type=Type.ID
            )

            aesgcm = AESGCM(kek)
            nonce = os.urandom(Symmetric.AESGCM_NONCE_LEN)
            ciphertext = aesgcm.encrypt(nonce, dek, None)
            
            try:
                with open("aes.key", "wb") as aes_key_file:
                    aes_key_file.write(salt)
                    aes_key_file.write(nonce)
                    aes_key_file.write(ciphertext)
            except OSError:
                print("Failed to write encrypted blob to aes.key")
                return
            
        return dek

    """
    Encrypts the given plaintext using AES

    Parameters: bytes object of the plaintext, data encryption key
    Returns: bytes object of the nonce, bytes object of the AES encrypted ciphertext
    """
    @staticmethod
    def encrypt_aes(plaintext: bytes, dek: bytes) -> Tuple[bytes, bytes]:
        aesgcm = AESGCM(dek)
        nonce = os.urandom(Symmetric.AESGCM_NONCE_LEN)

        ciphertext = aesgcm.encrypt(
            nonce, plaintext,
            associated_data=None
        )

        return nonce, ciphertext

    """
    Decrypts the given ciphertext using AES

    Parameters: bytes object of the ciphertext, data encryption key, and the nonce
    Returns: bytes object of the decrypted plaintext
    """
    @staticmethod
    def decrypt_aes(ciphertext: bytes, dek: bytes, nonce: bytes) -> bytes:
        aesgcm = AESGCM(dek)

        plaintext = aesgcm.decrypt(
            nonce, ciphertext,
            associated_data= None
        )

        return plaintext
    
    """
    Displays the AES key as hex.

    Parameters: AES key as a bytes object
    Returns: void
    """
    @staticmethod
    def display_key(key: bytes):
        print("THIS IS YOUR SECRET AES KEY. ONLY SHARE THIS KEY WITH PEOPLE YOU WANT TO BE ABLE TO READ YOUR MESSAGES.")
        print(key.hex())

            

"""
For RSA asymmetric encryption
"""
class Asymmetric:
    """
    Checks if an RSA private key file exists and either loads the key from that file
    or generates a new key and writes it to a file. The RSA public key is then derived from
    the private key.

    Parameters: the user's passphrase
    Returns: two bytes objects on success (private key and public key), and nothing on failure
    """
    @staticmethod
    def load_or_generate_key_pair(passphrase: str) -> Tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]:
        passphrase = passphrase.encode("utf-8")

        private_key = None
        public_key = None

        if Path("rsa_private.key").exists() and Path("rsa_private.key").is_file():
            try:
                with open("rsa_private.key", "rb") as rsa_private_key_file:
                    private_key = serialization.load_pem_private_key(
                        rsa_private_key_file.read(),
                        password=passphrase
                    )
            except FileNotFoundError:
                print("rsa_private.key file not found")
                return
            except OSError:
                print("Failed to read RSA private key from rsa_private.key")
                return
        else:
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048
            )

            pem_bytes = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.BestAvailableEncryption(passphrase)
            )
            try:
                with open("rsa_private.key", "wb") as rsa_private_key_file:
                    rsa_private_key_file.write(pem_bytes)
            except OSError:
                print("Failed to write RSA private key to rsa_private.key")
                return

        public_key = private_key.public_key()

        return private_key, public_key
    
    """
    Encrypts the given plaintext using RSA

    Parameters: plaintext in bytes, the RSA public key as an RSAPublicKey object
    Returns: ciphertext in bytes
    """
    @staticmethod
    def encrypt_rsa(plaintext: bytes, public_key: rsa.RSAPublicKey) -> bytes:
        ciphertext = public_key.encrypt(
            plaintext,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )

        return ciphertext
    
    """
    Decrypts the given ciphertext using RSA

    Parameters: ciphertext in bytes, the RSA private key as an RSAPrivateKey object
    Returns: plaintext in bytes
    """
    @staticmethod
    def decrypt_rsa(ciphertext: bytes, private_key: rsa.RSAPrivateKey) -> bytes:
        plaintext = private_key.decrypt(
            ciphertext,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )

        return plaintext

"""
Main function for testing
"""
def main():

    # setting passphrase
    passphrase = input("Enter your passphrase: ")
    
    # testing symmetric encryption
    
    print("SYMMETRIC ENCRYPTION TESTING: ")
    
    key = Symmetric.load_or_generate_key(passphrase)
    
    plaintext = input("Enter plaintext for symmetric testing: ")
    plaintext_b = plaintext.encode("utf-8")

    nonce, ciphertext = Symmetric.encrypt_aes(plaintext_b, key)
    print(f"AES ciphertext: {ciphertext.hex()}")

    decrypted_plaintext = Symmetric.decrypt_aes(ciphertext, key, nonce)
    print(f"Decrypted AES plaintext: {decrypted_plaintext.decode('utf-8')}")



    # testing asymmetric encryption

    print("ASYMMETRIC ENCRYPTION TESTING: ")

    private_key, public_key = Asymmetric.load_or_generate_key_pair(passphrase)

    plaintext = input("Enter plaintext for asymmetric testing: ")
    plaintext_b = plaintext.encode("utf-8")

    ciphertext = Asymmetric.encrypt_rsa(plaintext_b, public_key)
    print(f"RSA ciphertext: {ciphertext.hex()}")

    decrypted_plaintext = Asymmetric.decrypt_rsa(ciphertext, private_key)
    print(f"Decrypted RSA plaintext: {decrypted_plaintext.decode('utf-8')}")
    


    # testing key display

    print("KEY DISPLAY TESTING")

    print("AES key (hex): ")
    Symmetric.display_key(key)

if __name__ == "__main__":
    main()