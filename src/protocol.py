from datetime import datetime
import framing

MSG_TIMEOUT = 30
PAYLOAD_SIZE = 128

class Packetizer:
    def __init__(self):
        self.last_id = 0

    def get_packets(self, msg: bytes) -> list:
        num_packets = len(msg) / PAYLOAD_SIZE
        if not num_packets % 1 == 0:
            num_packets += 1
        
        chunks = []
        for i in range(num_packets):
            offset = i * PAYLOAD_SIZE

            if len(msg) >= offset + PAYLOAD_SIZE:
                chunks.append(msg[offset:offset + PAYLOAD_SIZE])
            else:
                chunks.append(msg[offset:len(msg)])
        
        msg_id = self.last_id + 1
        packets = []
        for i in range(len(chunks)):
            packets.append(framing.build_packet(msg_id, i, len(chunks), chunks[i]))
        
        self.last_id = msg_id
        return packets


class Reassembler:
    def __init__(self):
        self.messages = {}
    
    def clear_timeouts(self):
        to_delete = []

        for msg, start_time in self.messages.items():
            if (datetime.now() - start_time) > MSG_TIMEOUT:
                to_delete.append(msg)
        
        for msg in to_delete:
            self.messages.pop(msg, None)

    def add_packet(self, msg_id, seq, total, payload):
        if msg_id not in self.messages:
            self.messages[msg_id] = {
                "start_time": datetime.now(),
                "total": total,
                "chunks": {}
            }

        msg = self.messages[msg_id]
        msg["chunks"][seq] = payload

        if len(msg["chunks"]) == msg["total"]:
            data = b''.join(
                msg["chunks"][i]
                for i in range(msg["total"])
            )

            del self.messages[msg_id]

            return data
        
        return None