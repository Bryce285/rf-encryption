import socket
import json
import threading
import base64
import math
import numpy as np
from collections import deque

MAX_UDP_PAYLOAD = 1400

class RadioClient:
    def __init__(self, node_id, position=(0,0),
                 server_addr=("localhost", 5000),
                 local_port=5002, # THIS NEEDS TO BE UNIQUE FOR EACH CLIENT
                 channel="ch1"):

        self.node_id = node_id
        self.position = position
        self.channel = channel
        self.server_addr = server_addr

        self.partial_signals = {}

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("localhost", local_port))

        self.register()

        self.inbox = deque()
        threading.Thread(target=self.listen, daemon=True).start()

    def register(self):
        self.sock.sendto(json.dumps({
            "type": "register",
            "node_id": self.node_id,
            "channel": self.channel,
            "position": self.position
        }).encode(), self.server_addr)

    def switch_channel(self, new_channel):
        self.channel = new_channel
        self.sock.sendto(json.dumps({
            "type": "switch_channel",
            "node_id": self.node_id,
            "channel": new_channel
        }).encode(), self.server_addr)

    def send(self, signal: np.ndarray):
        """Send a large signal in UDP-safe chunks while keeping the interface the same."""
        raw_bytes = signal.tobytes()
        total_len = len(raw_bytes)
        num_chunks = math.ceil(total_len / MAX_UDP_PAYLOAD)

        for i in range(num_chunks):
            start = i * MAX_UDP_PAYLOAD
            end = min(start + MAX_UDP_PAYLOAD, total_len)
            chunk = raw_bytes[start:end]

            encoded = base64.b64encode(chunk).decode()

            packet = json.dumps({
                "type": "transmit",
                "node_id": self.node_id,
                "chunk_index": i,
                "num_chunks": num_chunks,
                "payload": encoded
            }).encode()

            self.sock.sendto(packet, self.server_addr)

    def listen(self):
        while True:
            data, _ = self.sock.recvfrom(65535)
            msg = json.loads(data.decode())

            if msg["type"] == "receive":
                key = msg["from"]

                if key not in self.partial_signals:
                    self.partial_signals[key] = {
                        "num_chunks": msg["num_chunks"],
                        "chunks": {}
                    }

                entry = self.partial_signals[key]
                entry["chunks"][msg["chunk_index"]] = base64.b64decode(msg["payload"])

                # check if complete
                if len(entry["chunks"]) == entry["num_chunks"]:

                    assembled = b''.join(
                        entry["chunks"][i]
                        for i in range(entry["num_chunks"])
                    )

                    signal = np.frombuffer(assembled, dtype=np.float64)

                    print("Full signal received:", len(signal))

                    self.inbox.append(signal)

                    del self.partial_signals[key]