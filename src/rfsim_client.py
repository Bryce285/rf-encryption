import socket
import json
import threading
import base64
import numpy as np
from collections import deque

class RadioClient:
    def __init__(self, node_id, position=(0,0),
                 server_addr=("localhost", 5000),
                 local_port=0,
                 channel="ch1"):

        self.node_id = node_id
        self.position = position
        self.channel = channel
        self.server_addr = server_addr

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

    def send(self, signal):
        encoded = base64.b64encode(signal.tobytes()).decode()
        self.sock.sendto(json.dumps({
            "type": "transmit",
            "node_id": self.node_id,
            "payload": encoded
        }).encode(), self.server_addr)

    def listen(self):
        while True:
            data, _ = self.sock.recvfrom(65535)
            msg = json.loads(data.decode())

            if msg["type"] == "receive":
                print("receiving message")
                payload = base64.b64decode(msg["payload"])
                signal = np.frombuffer(payload, dtype=np.float64)

                self.inbox.append(signal)