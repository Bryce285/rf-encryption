"""
Protocol module: message packetization and reassembly.

Packetizer splits outgoing messages into fixed-size chunks and wraps
them in framed packets.  Reassembler collects incoming packets and
reassembles complete messages, timing out stale partial messages.
"""

from datetime import datetime, timedelta
import framing
import math

# Maximum seconds to wait for all fragments of a message before discarding
MSG_TIMEOUT = 30
# Maximum payload bytes per packet
PAYLOAD_SIZE = 128


class Packetizer:
    """Splits a byte-string message into framed packets."""

    def __init__(self):
        self.last_id = 0  # auto-incrementing message counter

    def get_packets(self, msg: bytes) -> list:
        """
        Fragment *msg* and wrap each chunk in a framed packet.

        Returns a list of raw packet byte-strings ready for modulation.
        """
        # Calculate how many chunks we need (ceiling division)
        num_packets = math.ceil(len(msg) / PAYLOAD_SIZE)

        # Split the message into chunks
        chunks = []
        for i in range(num_packets):
            offset = i * PAYLOAD_SIZE
            chunks.append(msg[offset:offset + PAYLOAD_SIZE])

        # Build framed packets for each chunk
        msg_id = self.last_id + 1
        packets = []
        for i, chunk in enumerate(chunks):
            packets.append(framing.build_packet(msg_id, i, num_packets, chunk))

        self.last_id = msg_id
        return packets


class Reassembler:
    """
    Collects incoming packet fragments and reassembles complete messages.

    Each message is identified by its *msg_id* and tracked until all
    fragments arrive or the timeout expires.
    """

    def __init__(self):
        # msg_id -> {"start_time": datetime, "total": int, "chunks": {seq: bytes}}
        self.messages = {}

    def clear_timeouts(self):
        """Remove partially-assembled messages that have exceeded MSG_TIMEOUT."""
        to_delete = []

        for msg_id, msg_info in self.messages.items():
            # Compare timedelta with timedelta (not datetime with int)
            if (datetime.now() - msg_info["start_time"]) > timedelta(seconds=MSG_TIMEOUT):
                to_delete.append(msg_id)

        for msg_id in to_delete:
            self.messages.pop(msg_id, None)

    def add_packet(self, msg_id, seq, total, payload):
        """
        Register a received packet fragment.

        Returns the fully-reassembled message (bytes) once all fragments
        have arrived, or None if fragments are still missing.
        """
        if msg_id not in self.messages:
            self.messages[msg_id] = {
                "start_time": datetime.now(),
                "total": total,
                "chunks": {}
            }

        msg = self.messages[msg_id]
        msg["chunks"][seq] = payload

        # Check if all fragments have been received
        if len(msg["chunks"]) == msg["total"]:
            # Reassemble in order
            data = b''.join(
                msg["chunks"][i]
                for i in range(msg["total"])
            )
            del self.messages[msg_id]
            return data

        return None