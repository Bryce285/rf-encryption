"""
This file contains the classes of the encryption layer
"""

from cryptography.fernet import Fernet
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization

from typing import Tuple

"""
TODO
We need to decide on a protocol for sharing the symmetric key. This could be done
by either writing the key to a usb for the user to plug into the other device, or
we could just display the key as hex on the screen and have the user manually
enter it into the other device.
"""


"""
For AES symmetric encryption
"""
class Symmetric:
    """
    Checks if an AES key file exists and either loads the key from that file
    or generates a new key and writes it to a file

    Parameters: void
    Returns: AES key bytes
    """
    @staticmethod
    def load_or_generate_key() -> bytes:
        aes_key = b""
    
        if Path("aes.key").exists() and Path("aes.key").is_file():
            try:
                with open("aes.key", "rb") as aes_key_file:
                    aes_key = aes_key_file.read()
            except FileNotFoundError:
                print("aes.key file not found")
        else:
            aes_key = Fernet.generate_key()

            with open("aes.key", "wb") as aes_key_file:
                aes_key_file.write(aes_key)

        return aes_key

    """
    Loads an instance of Fernet from the given AES key

    Parameters: bytes object of the AES key
    Returns: Fernet instance
    """
    @staticmethod
    def load_fernet(aes_key: bytes) -> Fernet:
        return Fernet(aes_key)

    """
    Encrypts the given plaintext using AES

    Parameters: bytes object of the plaintext, Fernet object that has been initialized with the desired AES key
    Returns: bytes object of the AES encrypted ciphertext
    """
    @staticmethod
    def encrypt_aes(plaintext: bytes, fernet: Fernet) -> bytes:
        return fernet.encrypt(plaintext)

    """
    Decrypts the given ciphertext using AES

    Parameters: bytes object of the ciphertext, Fernet object that has been initialized with the desired AES key
    Returns: bytes object of the decrypted plaintext
    """
    @staticmethod
    def decrypt_aes(ciphertext: bytes, fernet: Fernet) -> bytes:
        return fernet.decrypt(ciphertext)


"""
For RSA asymmetric encryption
"""
class Asymmetric:
    """
    Checks if an RSA private key file exists and either loads the key from that file
    or generates a new key and writes it to a file. The RSA public key is then derived from
    the private key.

    Parameters: void
    Returns: two bytes objects, one of which is the private key, and the other is the public key
    """
    @staticmethod
    def load_or_generate_key_pair() -> Tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]:
        private_key = None
        public_key = None

        if Path("rsa_private.key").exists() and Path("rsa_private.key").is_file():
            try:
                with open("rsa_private.key", "rb") as rsa_private_key_file:
                    private_key = serialization.load_pem_private_key(
                        rsa_private_key_file.read(),
                        password=None
                    )
            except FileNotFoundError:
                print("rsa_private.key file not found")
        else:
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048
            )

            pem_bytes = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )

            with open("rsa_private.key", "wb") as rsa_private_key_file:
                rsa_private_key_file.write(pem_bytes)

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

    # testing symmetric encryption
    key = Symmetric.load_or_generate_key()
    fernet = Symmetric.load_fernet(key)

    plaintext = input("Enter plaintext for symmetric testing: ")
    plaintext_b = plaintext.encode("utf-8")

    ciphertext = Symmetric.encrypt_aes(plaintext_b, fernet)
    print(f"AES ciphertext: {ciphertext.hex()}")

    decrypted_plaintext = Symmetric.decrypt_aes(ciphertext, fernet)
    print(f"Decrypted AES plaintext: {decrypted_plaintext.decode("utf-8")}")

    # testing asymmetric encryption
    private_key, public_key = Asymmetric.load_or_generate_key_pair()

    plaintext = input("Enter plaintext for asymmetric testing: ")
    plaintext_b = plaintext.encode("utf-8")

    ciphertext = Asymmetric.encrypt_rsa(plaintext_b, public_key)
    print(f"RSA ciphertext: {ciphertext.hex()}")

    decrypted_plaintext = Asymmetric.decrypt_rsa(ciphertext, private_key)
    print(f"Decrypted RSA plaintext: {decrypted_plaintext.decode("utf-8")}")

if __name__ == "__main__":
    main()