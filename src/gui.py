"""
GUI module: PySimpleGUI front-end for the RF encrypted messaging app.

Layout
------
1. Setup window  - choose node ID, cipher, passphrase, output device, simulated.
2. Chat window   - scrolling message history, input field, send button.

The backend (key setup, encrypt/transmit, receive/decrypt) runs on a
background thread so the GUI stays responsive.  Received messages are
pushed to the main thread via PySimpleGUI's write_event_value() mechanism.
"""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Callable, Optional

import PySimpleGUI as sg
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

import crypto
import framing
import modulation
import protocol
from interface import Interface


# ── Colour palette (Catppuccin-inspired dark theme) ─────────────────────────
_BG      = "#1e1e2e"
_PANEL   = "#313244"
_ACCENT  = "#89b4fa"
_TEXT    = "#cdd6f4"
_SUBTEXT = "#a6adc8"
_GREEN   = "#a6e3a1"
_RED     = "#f38ba8"
_YELLOW  = "#f9e2af"

sg.theme_add_new("rfcrypt", {
    "BACKGROUND":    _BG,
    "TEXT":          _TEXT,
    "INPUT":         _PANEL,
    "TEXT_INPUT":    _TEXT,
    "SCROLL":        _PANEL,
    "BUTTON":       (_BG, _ACCENT),
    "PROGRESS":     (_ACCENT, _PANEL),
    "BORDER":        1,
    "SLIDER_DEPTH":  0,
    "PROGRESS_DEPTH": 0,
})
sg.theme("rfcrypt")

# Retransmission attempts before dropping a packet
_MAX_RETRIES = 3


# ── Backend ──────────────────────────────────────────────────────────────────

class GuiBackend:
    """
    Drop-in equivalent of pipeline.Cli, wired to a GUI callback instead of
    printing to stdout.

    Parameters
    ----------
    node_id : str
        Display name for this radio node.
    simulated : bool
        Route audio through the RF sim server when True.
    speaker_idx : int
        Original sounddevice output-device index.
    on_message : Callable[[str, str, str], None]
        Called on the RX thread each time a full plaintext message arrives.
        Signature: on_message(channel, cipher, plaintext)
    """

    def __init__(
        self,
        node_id: str,
        simulated: bool,
        speaker_idx: int,
        on_message: Callable[[str, str, str], None],
    ):
        self.interface    = Interface(node_id, simulated, speaker_idx)
        self.node_id      = node_id
        self.on_message   = on_message

        self.aes_dek: bytes                            = b""
        self.rsa_priv: Optional[rsa.RSAPrivateKey]    = None
        self.rsa_pub:  Optional[rsa.RSAPublicKey]     = None
        self.receiver_pub_key: Optional[rsa.RSAPublicKey] = None

        self.channel = "ch1"

        self._ack_event    = threading.Event()
        self._last_ack_seq = -1

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send_message(self, plaintext: str, cipher: str) -> bool:
        """
        Encrypt *plaintext* with *cipher* and transmit it.

        Returns True on success, False if RSA peer key is missing.
        """
        packetizer = protocol.Packetizer()
        msg_bytes  = plaintext.encode("utf-8")

        if cipher == "aes":
            nonce, ciphertext = crypto.Symmetric.encrypt_aes(msg_bytes, self.aes_dek)
            tx_payload = nonce + ciphertext
        else:
            if self.receiver_pub_key is None:
                return False
            tx_payload = crypto.Asymmetric.encrypt_rsa(msg_bytes, self.receiver_pub_key)

        self._send_with_ack(packetizer.get_packets(tx_payload))
        return True

    def start_receiver(self, cipher: str):
        """Spawn a daemon receive thread."""
        threading.Thread(
            target=self._receive_loop,
            args=(cipher,),
            daemon=True,
        ).start()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _send_with_ack(self, packets: list):
        for seq, packet in enumerate(packets):
            for attempt in range(1, _MAX_RETRIES + 1):
                # Clear the event BEFORE sending so that an ACK which arrives
                # during (or immediately after) transmission is not lost by a
                # subsequent clear() call.
                self._ack_event.clear()
                signal = modulation.text_to_afsk(packet)
                self.interface.send(signal, self.channel)

                if self._ack_event.wait(timeout=1.0) and self._last_ack_seq == seq:
                    break
                # silent retry — status updates come from the GUI layer

    def _receive_loop(self, cipher: str):
        reassembler = protocol.Reassembler()

        while True:
            reassembler.clear_timeouts()

            rx_msg = self.interface.receive()
            if rx_msg is None or rx_msg.size == 0:
                continue

            demodulated = modulation.afsk_to_text(rx_msg)

            # Out-of-band public-key exchange
            if demodulated.startswith(b"PUBKEY:"):
                pem_data = demodulated[len(b"PUBKEY:"):]
                try:
                    self.receiver_pub_key = serialization.load_pem_public_key(pem_data)
                except Exception:
                    pass
                continue

            # ACK packet
            ack_seq = framing.parse_ack(demodulated)
            if ack_seq is not None:
                self._last_ack_seq = ack_seq["seq"]
                self._ack_event.set()
                continue

            # Data packet
            parsed = framing.parse_packet(demodulated)
            if parsed is None:
                continue

            msg_id  = parsed.get("message_id")
            seq     = parsed.get("seq")
            total   = parsed.get("total")
            payload = parsed.get("payload")

            # Send ACK
            ack_packet = framing.build_ack(msg_id, seq)
            ack_signal = modulation.text_to_afsk(ack_packet)
            self.interface.send(ack_signal, self.channel)

            assembled = reassembler.add_packet(msg_id, seq, total, payload)
            if assembled is None:
                continue

            # Decrypt
            if cipher == "aes":
                nonce           = assembled[:crypto.Symmetric.AESGCM_NONCE_LEN]
                ciphertext      = assembled[crypto.Symmetric.AESGCM_NONCE_LEN:]
                plaintext_bytes = crypto.Symmetric.decrypt_aes(
                    ciphertext, self.aes_dek, nonce
                )
            else:
                plaintext_bytes = crypto.Asymmetric.decrypt_rsa(
                    assembled, self.rsa_priv
                )

            self.on_message(
                self.channel,
                cipher,
                plaintext_bytes.decode("utf-8", errors="replace"),
            )


# ── Setup window ─────────────────────────────────────────────────────────────

def _setup_window(output_devices: list[tuple[int, dict]]) -> dict | None:
    """
    Display the connection-setup window.

    Returns a settings dict on success, or None if the user closed the window.
    """
    device_names = [f"{orig_idx}: {d['name']}" for orig_idx, d in output_devices]

    layout = [
        [
            sg.Text(
                "RF Encrypted Messaging",
                font=("Helvetica", 18, "bold"),
                text_color=_ACCENT,
                background_color=_BG,
                justification="center",
                expand_x=True,
                pad=(0, (14, 6)),
            )
        ],
        [sg.HSeparator(color=_PANEL)],
        [
            sg.Text("Node ID",       size=(14, 1), background_color=_BG),
            sg.Input(key="-NODE-",   size=(26, 1), default_text="alice"),
        ],
        [
            sg.Text("Cipher",        size=(14, 1), background_color=_BG),
            sg.Combo(
                ["aes", "rsa"],
                default_value="aes",
                key="-CIPHER-",
                readonly=True,
                size=(24, 1),
            ),
        ],
        [
            sg.Text("Passphrase",    size=(14, 1), background_color=_BG),
            sg.Input(key="-PASS-",   size=(26, 1), password_char="●"),
        ],
        [
            sg.Text("Output device", size=(14, 1), background_color=_BG),
            sg.Combo(
                device_names,
                key="-DEVICE-",
                readonly=True,
                size=(40, 1),
                default_value=device_names[0] if device_names else "",
            ),
        ],
        [
            sg.Checkbox(
                "Simulated RF",
                key="-SIM-",
                background_color=_BG,
                text_color=_TEXT,
                default=False,
            )
        ],
        [sg.HSeparator(color=_PANEL, pad=(0, 10))],
        [
            sg.Push(background_color=_BG),
            sg.Button("Connect", size=(12, 1), button_color=(_BG, _ACCENT)),
            sg.Push(background_color=_BG),
        ],
    ]

    win = sg.Window(
        "rfcrypt — setup",
        layout,
        background_color=_BG,
        element_padding=(10, 7),
        finalize=True,
    )
    win["-NODE-"].set_focus()

    while True:
        event, values = win.read()
        if event in (sg.WIN_CLOSED,):
            win.close()
            return None

        if event == "Connect":
            node_id    = values["-NODE-"].strip()
            cipher     = values["-CIPHER-"]
            passphrase = values["-PASS-"]
            device_str = values["-DEVICE-"]
            simulated  = values["-SIM-"]

            errors = []
            if not node_id:
                errors.append("Node ID cannot be empty.")
            if not passphrase:
                errors.append("Passphrase cannot be empty.")
            if not device_str:
                errors.append("Please select an output device.")

            if errors:
                sg.popup_error("\n".join(errors), background_color=_BG, text_color=_TEXT)
                continue

            # "42: Built-in Speaker" → 42
            speaker_idx = int(device_str.split(":")[0])
            win.close()
            return {
                "node_id":     node_id,
                "cipher":      cipher,
                "passphrase":  passphrase,
                "speaker_idx": speaker_idx,
                "simulated":   simulated,
            }


# ── Chat window ───────────────────────────────────────────────────────────────

def _build_chat_window(node_id: str, cipher: str, channel: str) -> sg.Window:
    """Construct (but do not show) the main chat window."""

    header = f"  {node_id}  ·  cipher: {cipher}  ·  channel: {channel}"

    layout = [
        # Header bar
        [
            sg.Text(
                header,
                key="-HEADER-",
                background_color=_PANEL,
                text_color=_ACCENT,
                font=("Helvetica", 11, "bold"),
                expand_x=True,
                pad=(8, 6),
            )
        ],
        # Message history
        [
            sg.Multiline(
                key="-HISTORY-",
                size=(72, 24),
                disabled=True,
                autoscroll=True,
                background_color=_BG,
                text_color=_TEXT,
                font=("Courier", 10),
                expand_x=True,
                expand_y=True,
                write_only=False,
            )
        ],
        # Status bar
        [
            sg.Text(
                "",
                key="-STATUS-",
                size=(60, 1),
                background_color=_PANEL,
                text_color=_SUBTEXT,
                font=("Helvetica", 9),
                pad=(8, 3),
            )
        ],
        # Input row
        [
            sg.Input(
                key="-MSG-",
                expand_x=True,
                background_color=_PANEL,
                text_color=_TEXT,
                font=("Helvetica", 11),
            ),
            sg.Button(
                "Send",
                size=(8, 1),
                button_color=(_BG, _ACCENT),
                bind_return_key=True,
            ),
        ],
    ]

    return sg.Window(
        f"rfcrypt — {node_id}",
        layout,
        background_color=_BG,
        element_padding=(6, 4),
        resizable=True,
        finalize=True,
    )


# ── Entry-point ───────────────────────────────────────────────────────────────

def run():
    """Launch the full GUI application (called from pipeline.orchestrateGui)."""
    import sounddevice as sd

    devices        = sd.query_devices()
    output_devices = [
        (i, d) for i, d in enumerate(devices) if d["max_output_channels"] > 0
    ]

    settings = _setup_window(output_devices)
    if settings is None:
        return  # user closed setup window

    node_id     = settings["node_id"]
    cipher      = settings["cipher"]
    passphrase  = settings["passphrase"]
    speaker_idx = settings["speaker_idx"]
    simulated   = settings["simulated"]

    # Open chat window before blocking key-setup steps so the user sees progress
    win = _build_chat_window(node_id, cipher, "ch1")

    # ── Convenience helpers that touch window elements ──────────────────

    def _status(msg: str, color: str = _SUBTEXT):
        win["-STATUS-"].update(value=msg, text_color=color)

    def _append(line: str, color: str = _TEXT):
        win["-HISTORY-"].print(line, text_color=color, end="\n")

    # ── RX callback (called from background thread) ─────────────────────

    def _on_message(channel: str, recv_cipher: str, plaintext: str):
        win.write_event_value("-RX-", (channel, recv_cipher, plaintext))

    # ── Initialise backend ───────────────────────────────────────────────

    _status("Setting up keys…", _YELLOW)
    win.refresh()

    backend = GuiBackend(node_id, simulated, speaker_idx, _on_message)

    if cipher == "aes":
        try:
            backend.aes_dek = crypto.Symmetric.load_or_generate_key(passphrase)
        except Exception as exc:
            sg.popup_error(f"AES key setup failed:\n{exc}")
            win.close()
            return
    else:
        try:
            backend.rsa_priv, backend.rsa_pub = (
                crypto.Asymmetric.load_or_generate_key_pair(passphrase)
            )
        except Exception as exc:
            sg.popup_error(f"RSA key setup failed:\n{exc}")
            win.close()
            return

        # Broadcast our public key so the peer can encrypt to us
        pub_pem = backend.rsa_pub.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        key_signal = modulation.text_to_afsk(b"PUBKEY:" + pub_pem)
        backend.interface.send(key_signal, backend.channel)
        _status("Public key broadcast sent. Waiting for peer…", _YELLOW)
        win.refresh()

    backend.start_receiver(cipher)

    _status("Connected — ready to send.", _GREEN)
    win.refresh()
    _append(f"── Connected as {node_id}  [cipher={cipher}] ──", _ACCENT)

    # ── Main event loop ──────────────────────────────────────────────────

    while True:
        event, values = win.read(timeout=100)

        if event in (sg.WIN_CLOSED, None):
            break

        # ── Incoming message from RX thread ──────────────────────────
        if event == "-RX-":
            ch, _cph, msg = values["-RX-"]
            _append(f"[{_now()}] ← {msg}", _GREEN)
            _status(f"Message received on {ch}", _SUBTEXT)

        # ── Send button (or Enter key) ────────────────────────────────
        elif event in ("Send",):
            msg_text = values["-MSG-"].strip()
            if not msg_text:
                continue
            win["-MSG-"].update("")
            _status("Sending…", _YELLOW)
            win.refresh()

            # Offload the blocking transmit to its own thread
            def _do_send(text: str = msg_text):
                ok = backend.send_message(text, cipher)
                win.write_event_value("-SENT-", (text, ok))

            threading.Thread(target=_do_send, daemon=True).start()

        # ── Transmit result from send thread ─────────────────────────
        elif event == "-SENT-":
            text, ok = values["-SENT-"]
            if ok:
                _append(f"[{_now()}] → {text}", _ACCENT)
                _status("Sent.", _SUBTEXT)
            else:
                _status("Send failed — no peer public key for RSA.", _RED)

    win.close()


# ── Utility ───────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now().strftime("%H:%M:%S")
