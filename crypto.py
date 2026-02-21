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

import os
import subprocess
import platform



"""
For AES symmetric encryption
"""
class Symmetric:
    """
    Checks if an AES key file exists and either loads the key from that file
    or generates a new key and writes it to a file.

    Parameters: void
    Returns: AES key bytes on success, nothing on failure
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
                return
            except OSError:
                print("Failed to read AES key from aes.key")
                return
        else:
            aes_key = Fernet.generate_key()
            
            try:
                with open("aes.key", "wb") as aes_key_file:
                    aes_key_file.write(aes_key)
            except OSError:
                print("Failed to write AES key to aes.key")
                return

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
    Checks if a file path leads to a USB storage device. This function is currently only implemented for Linux
    because checking this information on Windows is a little more difficult.

    Parameters: the path to check
    Returns: true if the path leads to a USB storage device, false otherwise
    """
    @staticmethod
    def is_usb_linux(path: str) -> Tuple[bool, str]:
        if platform.system() != "Linux":
            raise Exception("Storage device-type checking is only available for Linux systems.")
        
        path = os.path.abspath(path)

        df_output = subprocess.check_output(["df", path]).decode().splitlines()
        device = df_output[1].split()[0]

        lsblk_output = subprocess.check_output(
            ["lsblk", "-no", "TRAN", device]
        ).decode().strip()

        return lsblk_output == "usb", device

    """
    Formats a usb device. This function currently only available for Linux.

    Parameters: the path of the usb device
    Returns: true on success, false on failure
    """
    @staticmethod
    def format_usb_linux(device_path: str) -> bool:
        if platform.system() != "Linux":
            raise Exception("USB formatting is only available for Linux systems.")

        user_confirm = input("WARNING: This operation will erase all data on the selected USB storage device. Do you want to continue? (Y / n): ")
        if user_confirm != "Y" or user_confirm != "y":
            print("USB write operation cancelled.")
            return False
        
        try:
            subprocess.run(['sudo', 'umount', device_path], check=False)
        except Exception:
            pass

        format_cmd = ['sudo', f'mkfs.ext4', '-F', device_path]

        print(f"Attempting to format device {device_path} to ext4...")
        try:
            subprocess.run(
                format_cmd, 
                check=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE
            )
            print("USB storage device formatted successfully.")
            return True
        except subprocess.CalledProcessError as e:
            print(f"An error occurred: {e.stderr.decode()}")
            return False
        except Exception as e:
            print(f"An unexpected error occured: {e}")
            return False
        
        

    """
    Formats a USB storage device and then writes the AES key to it. We only allow writes to USB 
    devices because we don't want users accidentally writing their keys to random directories. 
    Because is_usb() is currently only implemented for Linux, this means that key writes can 
    only be done on Linux. Non-Linux users should use the display_key() function to view their 
    AES key from the program, where they can then manually copy it for sharing.

    Parameters: the path to write to, and the key to write
    Returns: true on success, false on failure
    """
    @staticmethod
    def write_key_linux(path: str, key: bytes) -> bool:
        if platform.system() != "Linux":
            raise Exception("Writing AES keys to a file is only available for Linux systems.")
        
        is_usb, device_path = Symmetric.is_usb_linux(path)

        if is_usb:
            if not Symmetric.format_usb_linux:
                print("Failed to format USB storage device.")
                return False

            try:
                with open(path, "wb") as key_file:
                    key_file.write(key)
            except OSError:
                print("Failed to write key to USB storage device")
                return False
        else:
            print(path + " does not lead to a USB storage device.")
            print("Write operation Failed")
            return False
        
        return True
    
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

    Parameters: void
    Returns: two bytes objects on success (private key and public key), and nothing on failure
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
                encryption_algorithm=serialization.NoEncryption()
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



    # testing key display and USB writes
    print("AES key (hex): ")
    Symmetric.display_key(key)

    user_in = input("Enter a USB device that you don't care about. Press 'Y' when it is inserted: ")
    if user_in != "Y" or user_in != "y":
        print("Exiting")
        return
    
    user_in = input("Enter the path to the usb: ")
    
    if Symmetric.write_key_linux(user_in, key):
        print("AES key successfully written to USB storage device.")
    else:
        print("Failed to write AES key to USB storage device.")

if __name__ == "__main__":
    main()