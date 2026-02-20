"""
This file contains the functions of the encryption layer
"""

from cryptography.fernet import Fernet
from pathlib import Path

"""
TODO
We need to decide on a protocol for sharing the symmetric key. This could be done
by either writing the key to a usb for the user to plug into the other device, or
we could just display the key as hex on the screen and have the user manually
enter it into the other device.
"""

"""
Checks if an AES key file exists and either loads the key from that file
or generates a new key and writes it to a file

Parameters: void
Returns: AES key bytes
"""
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
def load_fernet(aes_key: bytes) -> Fernet:
    return Fernet(aes_key)

"""
Encrypts the given plaintext using AES

Parameters: bytes object of the plaintext, Fernet object that has been initialized with the desired AES key
Returns: bytes object of the AES encrypted ciphertext
"""
def encrypt_aes(plaintext: bytes, fernet: Fernet) -> bytes:
    return fernet.encrypt(plaintext)

"""
Decrypts the given ciphertext using AES

Parameters: bytes object of the ciphertext, Fernet object that has been initialized with the desired AES key
Returns: bytes object of the decrypted plaintext
"""
def decrypt_aes(ciphertext: bytes, fernet: Fernet) -> bytes:
    return fernet.decrypt(ciphertext)

"""
Main function for testing
"""
def main():
    key = load_or_generate_key()
    fernet = load_fernet(key)

    plaintext = input("Enter plaintext: ")
    plaintext_b = plaintext.encode("utf-8")

    ciphertext = encrypt_aes(plaintext_b, fernet)
    print(f"Ciphertext: {ciphertext.hex()}")

    decrypted_plaintext = decrypt_aes(ciphertext, fernet)
    print(f"Decrypted plaintext: {decrypted_plaintext.decode("utf-8")}")

if __name__ == "__main__":
    main()