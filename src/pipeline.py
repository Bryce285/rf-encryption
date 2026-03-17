"""
Pipeline module: high-level orchestration of the full messaging workflow.

CLI path:
    type message → encrypt → packetize → modulate → transmit
    receive → demodulate → reassemble → decrypt → display
"""

import cli
import crypto
import framing
import logging
import modulation
import protocol
import threading
from interface import Interface
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.patch_stdout import patch_stdout

# Setup logging
logging.basicConfig(
	filename='../log.txt',
	level=logging.DEBUG,
	format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

# Number of retransmission attempts before giving up on a packet
MAX_RETRIES = 3

class Cli:
    """
    Runs the CLI messaging loop.

    Manages key material, launches a background receiver thread,
    and handles user input in the foreground.
    """

    def __init__(self, node_id: str, simulated: bool, speaker_idx: int, mic_idx: int):
        self.interface = Interface(node_id, simulated, speaker_idx, mic_idx)
        self.node_id = node_id
        self.simulated = simulated

        # Crypto material (assigned during orchestrateCli)
        self.aes_dek: bytes = b""

        self.channel = "ch1"  # current RF channel

        # ACK synchronisation between rx-thread and tx-loop
        self.ack_event = threading.Event()
        self.last_ack_seq = -1


    # ------------------------------------------------------------------
    # Transmit helpers
    # ------------------------------------------------------------------
    def _send_with_ack(self, packets: list):
        """Modulate, transmit, and wait for per-packet ACKs with retries."""
        for seq, packet in enumerate(packets):
            for attempt in range(1, MAX_RETRIES + 1):
                signal = modulation.text_to_afsk(packet)
                logger.info(f"TX: packet {seq} ({len(packet)} B, {len(signal)} samples)")

                # Clear BEFORE sending so that an ACK arriving while
                # send() blocks isn't wiped out by a late clear().
                self.ack_event.clear()
                self.interface.send(signal, self.channel)

                if self.ack_event.wait(timeout=1.0) and self.last_ack_seq == seq:
                    break
                print(f"Retrying packet {seq} (attempt {attempt}/{MAX_RETRIES})")
            else:
                print(f"Failed to send packet {seq}, aborting message")
                return

    # ------------------------------------------------------------------
    # Background receiver
    # ------------------------------------------------------------------
    def receive_signal(self):
        """Continuously receive, demodulate, reassemble, and decrypt messages."""
        frame_decoder = framing.FrameDecoder()
        reassembler = protocol.Reassembler()

        while True:
            reassembler.clear_timeouts()

            # Poll the interface for an incoming signal
            rx_msg = self.interface.receive()
            if rx_msg is None or rx_msg.size == 0:
                continue

            print("signal received from interface")
            logger.info("RX samples: %s", len(rx_msg))

            # Demodulate AFSK audio back into raw bytes
            demodulated = modulation.afsk_to_text(rx_msg)

            logger.info("RX: %s", demodulated[:24])

            # --- Check if this is an ACK packet ---
            ack_seq = framing.parse_ack(demodulated)
            if ack_seq is not None:
                self.last_ack_seq = ack_seq["seq"]
                self.ack_event.set()
                logger.info("ACK event set")
                continue

            packets = frame_decoder.feed(demodulated)

            for parsed in packets:
                print("Packet has been parsed")

                msg_id = parsed["message_id"]
                seq = parsed["seq"]
                total = parsed["total"]
                payload = parsed["payload"]

                ack_packet = framing.build_ack(msg_id, seq)
                ack_signal = modulation.text_to_afsk(ack_packet)
                self.interface.send(ack_signal, self.channel)

                assembled = reassembler.add_packet(msg_id, seq, total, payload)
                if assembled is not None:

                    print("Packet assembled")

                    nonce = assembled[:crypto.Symmetric.AESGCM_NONCE_LEN]
                    ciphertext = assembled[crypto.Symmetric.AESGCM_NONCE_LEN:]
                    plaintext_bytes = crypto.Symmetric.decrypt_aes(
                        ciphertext, self.aes_dek, nonce
                    )

                    cli.print_msg(
                        self.channel,
                        plaintext_bytes.decode("utf-8", errors="replace")
                    )

    # ------------------------------------------------------------------
    # Main CLI loop
    # ------------------------------------------------------------------
    def orchestrateCli(self):
        """Initialise keys and run the send loop (with background rx thread)."""

        # --- Key setup ---
        passphrase = input(f'{cli._header(self.channel)} Enter your passphrase: ')
        self.aes_dek = crypto.Symmetric.load_or_generate_key(passphrase)

        # Start background receive thread
        threading.Thread(target=self.receive_signal, daemon=True).start()

        # --- Send loop with prompt_toolkit for clean concurrent I/O ---
        session = PromptSession()
        packetizer = protocol.Packetizer()
        
        with patch_stdout():
            while True:
                # Now prompt for input (won't be disrupted by background messages)
                try:
                    msg = session.prompt(f"{cli.get_msg(self.channel)}")
                except KeyboardInterrupt:
                    print("\nExiting...")
                    break

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
                msg_bytes = msg.encode("utf-8")
                nonce, ciphertext = crypto.Symmetric.encrypt_aes(msg_bytes, self.aes_dek)
                tx_payload = nonce + ciphertext

                self._send_with_ack(packetizer.get_packets(tx_payload))

def orchestrateGui():
    """Launch the PySimpleGUI front-end."""
    import gui
    gui.run()