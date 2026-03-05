# High-level orchestration: record → encrypt → modulate → play, and reverse pipeline for demodulation → decryption

import cli
import crypto
import modulation
import threading
from interface import Interface

# TODO - need to chunk the data when we send it and have a reassembly protocol when we receive

class Cli:
    def __init__(self, id: str, simulated: bool):
        self.interface = Interface(id, simulated)
        self.id = id
        self.simulated = simulated
        self.aes_dek: bytes
        self.rsa_priv: bytes
        self.rsa_pub: bytes
        self.receiver_pub_key: bytes
        self.channel = "ch1"

    def receive_signal(self, cipher: str):
        while True:
            plaintext = ""

            if cipher == "aes":
                rx_msg = self.interface.receive()
                if rx_msg is None or rx_msg.size == 0:
                    continue

                print("received message from interface")

                demodulated_rx = modulation.afsk_to_text(rx_msg)
                nonce = demodulated_rx[:crypto.Symmetric.AESGCM_NONCE_LEN]
                ciphertext = demodulated_rx[crypto.Symmetric.AESGCM_NONCE_LEN:len(demodulated_rx):]

                print("Nonce type:", type(nonce))
                print("Nonce length:", len(nonce))      
                plaintext = crypto.Symmetric.decrypt_aes(ciphertext, self.aes_dek, nonce)
            else:
                rx_msg = self.interface.receive()
                if rx_msg is None or rx_msg.size == 0:
                    continue

                ciphertext = modulation.afsk_to_text(rx_msg)
                plaintext = crypto.Asymmetric.decrypt_rsa(ciphertext, self.rsa_priv)

            cli.print_msg(self.channel, cipher, plaintext)

    def orchestrateCli(self, cipher: str):
        if cipher != "aes" and cipher != "rsa":
            raise RuntimeError("Invalid cipher")
    
        quit = False

        passphrase = input('\033[1m' + '[rfcrypt]' + '\033[0m' + ' Enter your passphrase: ')
        if cipher == "aes":
            self.aes_dek = crypto.Symmetric.load_or_generate_key(passphrase)
        else:
            self.rsa_priv, self.rsa_pub = crypto.Asymmetric.load_or_generate_key_pair(passphrase)

            # TODO - exchange public keys, get receiver public key (perchance use key fingerprint instead of the full key)

        threading.Thread(target=self.receive_signal, args=(cipher,), daemon=True).start()
        while quit == False:
            msg = cli.get_msg(1, cipher)

            if msg.startswith("\\SYSCMD"):
                msg = msg[len("\\SYSCMD"):len(msg) - 1]
                field, value = cli.parse_cmd(msg)

                if field == "" or value == "":
                    print("Unrecognized system command.")
                elif field == "channel":
                    self.channel = value

                continue

            msg = msg.encode("utf-8")

            if cipher == "aes":
                nonce, ciphertext = crypto.Symmetric.encrypt_aes(msg, self.aes_dek)

                tx_msg = (nonce + ciphertext)
                signal = modulation.text_to_afsk(tx_msg)
                self.interface.send(signal, self.channel)

            
            else:
                ciphertext = crypto.Asymmetric.encrypt_rsa(msg, self.receiver_pub_key)

                signal = modulation.text_to_afsk(ciphertext)
                self.interface.send(signal, self.channel)


def orchestrateGui():
    pass