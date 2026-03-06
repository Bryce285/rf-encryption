"""
Pipeline module: high-level orchestration of the full messaging workflow.

CLI path:
    type message → encrypt → packetize → modulate (AFSK) → transmit
    receive → demodulate → reassemble → decrypt → display

GUI path:
    (placeholder — not yet implemented)
"""

import cli
import crypto
import modulation
import threading
import time
import framing
from interface import Interface
import protocol
from cryptography.hazmat.primitives import serialization

# Number of retransmission attempts before giving up on a packet
MAX_RETRIES = 3


class Cli:
    """
    Runs the CLI messaging loop.

    Manages key material, launches a background receiver thread,
    and handles user input in the foreground.
    """

    def __init__(self, node_id: str, simulated: bool, speaker_idx: int):
        self.interface = Interface(node_id, simulated, speaker_idx)
        self.node_id = node_id
        self.simulated = simulated

        # Crypto material (assigned during orchestrateCli)
        self.aes_dek: bytes
        self.rsa_priv: bytes
        self.rsa_pub: bytes
        self.receiver_pub_key: bytes

        self.channel = "ch1"  # current RF channel

        # ACK synchronisation between rx-thread and tx-loop
        self.ack_event = threading.Event()
        self.last_ack_seq = -1

    # ------------------------------------------------------------------
    # Background receiver
    # ------------------------------------------------------------------
    def receive_signal(self, cipher: str):
        """Continuously receive, demodulate, reassemble, and decrypt messages."""
        reassembler = protocol.Reassembler()

        while True:
            reassembler.clear_timeouts()

            # Poll the interface for an incoming signal
            rx_msg = self.interface.receive()
            if rx_msg is None or rx_msg.size == 0:
                continue

            print("signal received from interface")
            print("RX samples:", len(rx_msg))

            # Demodulate AFSK audio back into raw bytes
            demodulated = modulation.afsk_to_text(rx_msg)

            # --- Handle out-of-band PUBKEY exchange messages ---
            if demodulated.startswith(b"PUBKEY:"):
                pem_data = demodulated[len(b"PUBKEY:"):]
                try:
                    self.receiver_pub_key = serialization.load_pem_public_key(pem_data)
                    print("Received remote peer's public key (via rx thread).")
                except Exception as e:
                    print(f"Failed to parse received public key: {e}")
                continue

            print("RX:", demodulated[:24])

            # --- Check if this is an ACK packet ---
            ack_seq = framing.parse_ack(demodulated)
            if ack_seq is not None:
                self.last_ack_seq = ack_seq["seq"]
                self.ack_event.set()
                print("ACK event set")
                continue

            # --- Otherwise treat as a data packet ---
            parsed = framing.parse_packet(demodulated)
            if parsed is not None:

                print("Packet has been parsed")

                msg_id  = parsed.get("message_id")
                seq     = parsed.get("seq")
                total   = parsed.get("total")
                payload = parsed.get("payload")

                # Send ACK back to the transmitter
                ack_packet = framing.build_ack(msg_id, seq)
                ack_signal = modulation.text_to_afsk(ack_packet)
                self.interface.send(ack_signal, self.channel)

                # Attempt to reassemble the full message
                assembled = reassembler.add_packet(msg_id, seq, total, payload)
                if assembled is not None:

                    print("Packet assembled")

                    # Decrypt the reassembled ciphertext
                    if cipher == "aes":
                        nonce = assembled[:crypto.Symmetric.AESGCM_NONCE_LEN]
                        ciphertext = assembled[crypto.Symmetric.AESGCM_NONCE_LEN:]
                        plaintext_bytes = crypto.Symmetric.decrypt_aes(ciphertext, self.aes_dek, nonce)
                    else:
                        plaintext_bytes = crypto.Asymmetric.decrypt_rsa(assembled, self.rsa_priv)

                    # Decode bytes to string before printing
                    cli.print_msg(self.channel, cipher, plaintext_bytes.decode("utf-8", errors="replace"))

    # ------------------------------------------------------------------
    # Main CLI loop
    # ------------------------------------------------------------------
    def orchestrateCli(self, cipher: str):
        """Initialise keys and run the send loop (with background rx thread)."""
        if cipher not in ("aes", "rsa"):
            raise RuntimeError("Invalid cipher — must be 'aes' or 'rsa'")

        # --- Key setup ---
        passphrase = input('\033[1m' + '[rfcrypt]' + '\033[0m' + ' Enter your passphrase: ')
        if cipher == "aes":
            self.aes_dek = crypto.Symmetric.load_or_generate_key(passphrase)
        else:
            self.rsa_priv, self.rsa_pub = crypto.Asymmetric.load_or_generate_key_pair(passphrase)

            # --- RSA public-key exchange over the simulated channel ---
            # Serialize our public key to PEM bytes and broadcast it.
            pub_pem = self.rsa_pub.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            # Send a special "PUBKEY" framed message so the receiver can
            # parse it out of band.
            key_payload = b"PUBKEY:" + pub_pem
            key_signal = modulation.text_to_afsk(key_payload)
            self.interface.send(key_signal, self.channel)
            print("Public key broadcast sent.")

            # Wait for the remote peer's public key to arrive
            print("Waiting for remote peer's public key...")
            while not hasattr(self, 'receiver_pub_key') or self.receiver_pub_key is None:
                self.receiver_pub_key = None  # ensure attribute exists
                rx = self.interface.receive()
                if rx is None:
                    time.sleep(0.2)
                    continue
                raw = modulation.afsk_to_text(rx)
                if raw.startswith(b"PUBKEY:"):
                    pem_data = raw[len(b"PUBKEY:"):]
                    self.receiver_pub_key = serialization.load_pem_public_key(pem_data)
                    print("Received remote peer's public key.")
                    break
                time.sleep(0.1)

        # Start background receive thread
        threading.Thread(target=self.receive_signal, args=(cipher,), daemon=True).start()

        # --- Send loop ---
        packetizer = protocol.Packetizer()
        while True:
            msg = cli.get_msg(self.channel, cipher)

            # --- Handle system commands (e.g. \SYSCMD channel=ch2) ---
            if msg.startswith("\\SYSCMD"):
                msg = msg[len("\\SYSCMD"):].strip()
                field, value = cli.parse_cmd(msg)

                if field == "" or value == "":
                    print("Unrecognized system command.")
                elif field == "channel":
                    self.channel = value

                continue

            # --- Encrypt and transmit ---
            msg = msg.encode("utf-8")

            if cipher == "aes":
                # AES: prepend nonce to ciphertext, packetize, modulate, send
                nonce, ciphertext = crypto.Symmetric.encrypt_aes(msg, self.aes_dek)

                tx_msg = (nonce + ciphertext)
                packets = packetizer.get_packets(tx_msg)

                for seq, packet in enumerate(packets):
                    retries = 0

                    while retries < MAX_RETRIES:
                        print(f"TX: packet {seq} ({len(packet)} bytes)")

                        # Modulate the packet into an AFSK audio signal
                        signal = modulation.text_to_afsk(packet)
                        print("TX samples:", len(signal))

                        self.interface.send(signal, self.channel)

                        # Wait for an ACK from the receiver
                        self.ack_event.clear()
                        if self.ack_event.wait(timeout=1.0):
                            if self.last_ack_seq == seq:
                                break
                        else:
                            retries += 1
                            print(f"Retrying packet {seq} (attempt {retries}/{MAX_RETRIES})")

                    if retries == MAX_RETRIES:
                        print(f"Failed to send packet {seq}, aborting message")
                        break

            else:
                # RSA: encrypt, packetize with ACK, modulate, and send
                ciphertext = crypto.Asymmetric.encrypt_rsa(msg, self.receiver_pub_key)

                packets = packetizer.get_packets(ciphertext)

                for seq, packet in enumerate(packets):
                    retries = 0

                    while retries < MAX_RETRIES:
                        print(f"TX (RSA): packet {seq} ({len(packet)} bytes)")

                        signal = modulation.text_to_afsk(packet)
                        print("TX samples:", len(signal))

                        self.interface.send(signal, self.channel)

                        self.ack_event.clear()
                        if self.ack_event.wait(timeout=1.0):
                            if self.last_ack_seq == seq:
                                break
                        else:
                            retries += 1
                            print(f"Retrying packet {seq} (attempt {retries}/{MAX_RETRIES})")

                    if retries == MAX_RETRIES:
                        print(f"Failed to send packet {seq}, aborting message")
                        break


def orchestrateGui():
    """Launch the PySimpleGUI front-end (not yet implemented)."""
    pass