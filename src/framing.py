# Preamble/sync header insertion, error correction coding

import struct
import zlib
import reedsolo

# Reed-Solomon encoding and decoding
def encode_reed_solomon(data):
    rs = reedsolo.RSCodec(10)  # Adds 10 bytes of Reed-Solomon error correction
    return rs.encode(data.encode('utf-8')).decode('latin1')

def decode_reed_solomon(data):
    rs = reedsolo.RSCodec(10)
    return rs.decode(data.encode('latin1')).decode('utf-8')

# Preamble functions
def add_preamble(data, preamble="101010101010"):
    return preamble + data

def remove_preamble(data, preamble="101010101010"):
    if data.startswith(preamble):
        return data[len(preamble):]
    else:
        raise ValueError("Preamble not found")



PREAMBLE = b'\x55' * 20
SYNC = b'\xD3\x91'
HEADER_FORMAT = "!BBHHHH"
HEADER_SIZE = struct.calcsize("!BBHHHH")
CRC_FORMAT = "!I"
VERSION = 1
TYPE_DATA = 0x01

ACK_FORMAT = "!BHHH"
ACK_SIZE = struct.calcsize("!BHHH")
TYPE_ACK = 0x02

def build_packet(message_id, seq, total, payload: bytes):
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
    if not packet.startswith(PREAMBLE + SYNC):
        return None
    
    offset = len(PREAMBLE) + len(SYNC)

    header = packet[offset:offset + HEADER_SIZE]
    offset += HEADER_SIZE

    version, pkt_type, msg_id, seq, total, payload_len = \
        struct.unpack(HEADER_FORMAT, header)
    
    payload = packet[offset:offset + payload_len]
    offest += payload_len

    received_crc = struct.unpack("!I", packet[offset:offset+4])[0]

    computed_crc = zlib.crc32(header + payload) & 0xffffffff

    if received_crc != computed_crc:
        return None
    
    return {
        "version:": version,
        "type": pkt_type,
        "message_id": msg_id,
        "seq": seq,
        "total": total,
        "payload": payload
    }

def build_ack(msg_id, seq):
    packet = struct.pack(
        ACK_FORMAT,
        TYPE_ACK,
        msg_id,
        seq
    )

    return packet

def parse_ack(packet: bytes):
    if len(packet) < ACK_SIZE:
        return None

    pkt_type, msg_id, seq = struct.unpack(ACK_FORMAT, packet[:ACK_SIZE])

    if pkt_type != TYPE_ACK:
        return None

    return {
        "type": pkt_type,
        "message_id": msg_id,
        "seq": seq
    }