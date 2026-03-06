# High-level orchestration: record → encrypt → modulate → play, and reverse pipeline for demodulation → decryption

import cli
import crypto
import modulation
import threading
import framing
from interface import Interface
import protocol

MAX_RETRIES = 3

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
        self.ack_event = threading.Event()
        self.last_ack_seq = -1

    def receive_signal(self, cipher: str):
        reassembler = protocol.Reassembler()

        while True:
            reassembler.clear_timeouts()
            
            rx_msg = self.interface.receive()
            if rx_msg is None or rx_msg.size == 0:
                continue
            
            print("signal received from interface")
            print("RX samples:", len(rx_msg))

            demodulated = modulation.afsk_to_text(rx_msg)
            
            print("RX:", demodulated[:24])
            
            ack_seq = framing.parse_ack(demodulated)
            if ack_seq is not None:
                self.last_ack_seq = ack_seq["seq"]
                self.ack_event.set()
                print("ACK event set")
                continue

            parsed = framing.parse_packet(demodulated)
            if parsed is not None:
                
                print("Packet has been parsed")
                
                msg_id = parsed.get("message_id")
                seq = parsed.get("seq")
                total = parsed.get("total")
                payload = parsed.get("payload")

                ack_packet = framing.build_ack(msg_id, seq)
                ack_signal = modulation.text_to_afsk(ack_packet)
                self.interface.send(ack_signal, self.channel)

                assembled = reassembler.add_packet(msg_id, seq, total, payload)
                if assembled is not None:

                    print("Packet assembled")

                    if cipher == "aes":
                        nonce = assembled[:crypto.Symmetric.AESGCM_NONCE_LEN]
                        ciphertext = assembled[crypto.Symmetric.AESGCM_NONCE_LEN:]
                        plaintext = crypto.Symmetric.decrypt_aes(ciphertext, self.aes_dek, nonce)
                    else:
                        plaintext = crypto.Asymmetric.decrypt_rsa(assembled, self.rsa_priv)
            
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
            packetizer = protocol.Packetizer()
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
                packets = packetizer.get_packets(tx_msg)

                for seq, packet in enumerate(packets):
                    retries = 0

                    while retries < MAX_RETRIES:
                        print("TX:", packet[:24])

                        signal = modulation.text_to_afsk(packet)

                        print("TX samples:", len(signal))

                        self.interface.send(signal, self.channel)

                        self.ack_event.clear()
                        if self.ack_event.wait(timeout=1.0):
                            if self.last_ack_seq == seq:
                                break
                        else:
                            retries += 1
                            print(f"Retrying packet {seq}")
                    
                    if retries == MAX_RETRIES:
                        print(f"Failed to send packet {seq}, aborting message")
                        break
                        
            else:
                # TODO - need to update the rsa sending to match the above pattern
                ciphertext = crypto.Asymmetric.encrypt_rsa(msg, self.receiver_pub_key)

                signal = modulation.text_to_afsk(ciphertext)
                self.interface.send(signal, self.channel)


def orchestrateGui():
    pass