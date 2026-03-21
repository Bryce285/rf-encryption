"""
Framing module: packet construction, CRC verification, and Reed-Solomon
error correction.

Defines the binary wire format:
    [PREAMBLE][SYNC][HEADER][PAYLOAD][CRC32]

Also provides simple preamble helpers and ACK packet support.
"""

import struct
import zlib

# ---------------------------------------------------------------
# Binary packet format constants
# ---------------------------------------------------------------

PREAMBLE = b'\x55' * 20          # 20-byte alternating-bit preamble for clock recovery
SYNC     = b'\xD3\x91'            # 2-byte sync word marking start of header
HEADER_FORMAT = "!BBHHHH"         # version, type, msg_id, seq, total, payload_len
HEADER_SIZE   = struct.calcsize(HEADER_FORMAT)
CRC_FORMAT    = "!I"              # unsigned 32-bit CRC
VERSION       = 1
TYPE_DATA     = 0x01

ACK_FORMAT = "!BHH"               # type, msg_id, seq
ACK_SIZE   = struct.calcsize(ACK_FORMAT)
TYPE_ACK   = 0x02


# ---------------------------------------------------------------
# Data packet construction / parsing
# ---------------------------------------------------------------

def build_packet(message_id, seq, total, payload: bytes):
    """Build a framed data packet with CRC32 integrity check."""
    packet_type = TYPE_DATA
    payload_len = len(payload)

    header = struct.pack(
        HEADER_FORMAT,
        VERSION,
        packet_type,
        message_id,
        seq,
        total,
        payload_len
    )

    crc_input = header + payload
    crc = zlib.crc32(crc_input) & 0xffffffff
    crc_bytes = struct.pack(CRC_FORMAT, crc)

    packet = PREAMBLE + SYNC + header + payload + crc_bytes
    return packet

def parse_packet(packet: bytes):
    """Parse a framed data packet and verify its CRC.  Returns dict or None."""
    if not packet.startswith(PREAMBLE + SYNC):
        print("does not start with preamble and sync")
        return None
    
    offset = len(PREAMBLE) + len(SYNC)

    header = packet[offset:offset + HEADER_SIZE]
    offset += HEADER_SIZE

    version, pkt_type, msg_id, seq, total, payload_len = \
        struct.unpack(HEADER_FORMAT, header)
    
    payload = packet[offset:offset + payload_len]
    offset += payload_len

    received_crc = struct.unpack("!I", packet[offset:offset+4])[0]

    computed_crc = zlib.crc32(header + payload) & 0xffffffff

    if received_crc != computed_crc:
        print("crc does not match")
        return None
    
    return {
        "version": version,
        "type": pkt_type,
        "message_id": msg_id,
        "seq": seq,
        "total": total,
        "payload": payload
    }

# ---------------------------------------------------------------
# ACK packet construction / parsing
# ---------------------------------------------------------------

def build_ack(msg_id, seq):
    """Build a lightweight ACK packet (no CRC, no preamble)."""
    packet = struct.pack(
        ACK_FORMAT,
        TYPE_ACK,
        msg_id,
        seq
    )

    return packet

def parse_ack(packet: bytes):
    """Parse an ACK packet.  Returns dict or None."""
    if len(packet) != ACK_SIZE:
        return None

    pkt_type, msg_id, seq = struct.unpack(ACK_FORMAT, packet[:ACK_SIZE])

    if pkt_type != TYPE_ACK:
        return None

    return {
        "type": pkt_type,
        "message_id": msg_id,
        "seq": seq
    }


# ---------------------------------------------------------------
# Frame decoder for parsing data stream into packets
# ---------------------------------------------------------------

class FrameDecoder:
    def __init__(self):
        self.buffer = b''
        self.sync_word = PREAMBLE + SYNC

    def feed(self, data: bytes):
        self.buffer += data
        packets = []

        while True:
            start = self.buffer.find(self.sync_word)
            if start == -1:
                self.buffer = b''
                break

            if start > 0:
                self.buffer = self.buffer[start:]

            if len(self.buffer) < len(self.sync_word) + HEADER_SIZE:
                break

            offset = len(self.sync_word)

            header = self.buffer[offset:offset + HEADER_SIZE]
            try:
                version, pkt_type, msg_id, seq, total, payload_len = \
                    struct.unpack(HEADER_FORMAT, header)
            except struct.error:
                self.buffer = self.buffer[len(self.sync_word):]
                continue

            full_size = (
                len(self.sync_word) +
                HEADER_SIZE +
                payload_len +
                4
            )

            if len(self.buffer) < full_size:
                break

            frame = self.buffer[:full_size]
            self.buffer = self.buffer[full_size:]

            parsed = parse_packet(frame)
            if parsed:
                packets.append(parsed)

        return packets