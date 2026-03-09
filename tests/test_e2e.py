#!/usr/bin/env python3
"""
End-to-end integration test for the RF encryption messaging pipeline.

Spins up:
  1. The RF simulation server
  2. Two RadioClient nodes (alice, bob) on the same channel
  3. Encrypts a message on alice's side, modulates it, transmits through the
     sim server, then demodulates and decrypts on bob's side.

Validates that the decrypted plaintext matches the original message.
"""

import sys, os, time, threading

# Ensure src/ is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'rfsim_server'))

import numpy as np
import modulation
import framing
import protocol
import crypto
from rfsim_client import RadioClient
from sim_server import RadioSimServer


# ---------------------------------------------------------------------------
# 1. Start the sim server in a background thread
# ---------------------------------------------------------------------------
print("Starting RadioSim server...")
server = RadioSimServer(host="localhost", port=5555)
server_thread = threading.Thread(target=server.start, daemon=True)
server_thread.start()
time.sleep(0.3)  # let it bind


# ---------------------------------------------------------------------------
# 2. Create two clients (auto-assigned ports via local_port=0)
# ---------------------------------------------------------------------------
print("Creating clients alice and bob...")
alice = RadioClient("alice", position=(0, 0), server_addr=("localhost", 5555), local_port=0, channel="ch1")
bob   = RadioClient("bob",   position=(0, 0), server_addr=("localhost", 5555), local_port=0, channel="ch1")
time.sleep(0.3)  # let registrations settle


# ---------------------------------------------------------------------------
# 3. AES key setup — both sides share the same passphrase / key
# ---------------------------------------------------------------------------
passphrase = "test-passphrase-123"

# Remove any leftover key files from previous runs
if os.path.exists("aes.key"):
    os.remove("aes.key")

aes_key = crypto.Symmetric.load_or_generate_key(passphrase)
print(f"AES key generated: {aes_key.hex()[:16]}...")


# ---------------------------------------------------------------------------
# 4. Alice encrypts, packetizes, modulates, and sends
# ---------------------------------------------------------------------------
original_message = "Hello from Alice! 🔐 This is an encrypted RF test."
print(f"\nAlice sends: {original_message}")

plaintext_bytes = original_message.encode("utf-8")
nonce, ciphertext = crypto.Symmetric.encrypt_aes(plaintext_bytes, aes_key)
tx_payload = nonce + ciphertext

packetizer = protocol.Packetizer()
packets = packetizer.get_packets(tx_payload)
print(f"Packetized into {len(packets)} packet(s)")

for pkt in packets:
    signal = modulation.text_to_afsk(pkt)
    alice.send(signal)
    time.sleep(0.1)  # small gap between packets

print("Alice finished sending.")


# ---------------------------------------------------------------------------
# 5. Bob receives, demodulates, reassembles, decrypts
# ---------------------------------------------------------------------------
print("\nBob waiting for messages...")
reassembler = protocol.Reassembler()
deadline = time.time() + 10  # 10-second timeout

result = None
while time.time() < deadline:
    if not bob.inbox:
        time.sleep(0.1)
        continue

    rx_signal = bob.inbox.popleft()
    demodulated = modulation.afsk_to_text(rx_signal)

    # Try to parse as a data packet
    parsed = framing.parse_packet(demodulated)
    if parsed is None:
        continue

    msg_id  = parsed["message_id"]
    seq     = parsed["seq"]
    total   = parsed["total"]
    payload = parsed["payload"]

    assembled = reassembler.add_packet(msg_id, seq, total, payload)
    if assembled is not None:
        # Decrypt
        rx_nonce = assembled[:crypto.Symmetric.AESGCM_NONCE_LEN]
        rx_ct    = assembled[crypto.Symmetric.AESGCM_NONCE_LEN:]
        result   = crypto.Symmetric.decrypt_aes(rx_ct, aes_key, rx_nonce)
        break


# ---------------------------------------------------------------------------
# 6. Verify
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
if result is None:
    print("FAIL: Bob never received a complete message.")
    sys.exit(1)

decoded = result.decode("utf-8")
print(f"Bob received: {decoded}")

if decoded == original_message:
    print("PASS: Messages match!")
    sys.exit(0)
else:
    print(f"FAIL: Expected '{original_message}', got '{decoded}'")
    sys.exit(1)
