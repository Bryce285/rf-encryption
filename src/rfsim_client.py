"""
RF Simulation Client: UDP-based radio node that communicates with the
RF simulation server (sim_server.py).

Handles node registration, channel switching, chunked signal transmission
(large numpy arrays split into UDP-safe packets), and background
listening / reassembly of incoming signals.
"""

import socket
import json
import threading
import base64
import math
import numpy as np
from collections import deque

# Maximum raw bytes per UDP chunk (base64-encoded in the datagram).
# On localhost the loopback MTU is 65535, so large chunks are fine.
MAX_UDP_PAYLOAD = 48000

class RadioClient:
    def __init__(self, node_id, position=(0,0),
                 server_addr=("localhost", 5000),
                 local_port=0,
                 channel="ch1"):

        self.node_id = node_id
        self.position = position
        self.channel = channel
        self.server_addr = server_addr

        self.partial_transports = {}
        self.transport_counter = 0

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2 * 1024 * 1024)
        # Bind to port 0 so the OS assigns a free ephemeral port.
        # This allows multiple clients on the same machine without conflicts.
        self.sock.bind(("localhost", local_port))
        actual_port = self.sock.getsockname()[1]
        print(f"RadioClient '{node_id}' bound to port {actual_port}")

        self.register()

        self.inbox = deque()
        threading.Thread(target=self.listen, daemon=True).start()

    def _next_transport_id(self):
        self.transport_counter += 1
        return f"{self.node_id}-{self.transport_counter}"

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
        raw_bytes = signal.tobytes()

        transport_id = self._next_transport_id()
        chunk_size = MAX_UDP_PAYLOAD
        total = math.ceil(len(raw_bytes) / chunk_size)

        for i in range(total):
            chunk = raw_bytes[i*chunk_size:(i+1)*chunk_size]

            packet = json.dumps({
                "type": "transport",
                "node_id": self.node_id,
                "id": transport_id,
                "seq": i,
                "total": total,
                "payload": base64.b64encode(chunk).decode()
            }).encode()

            self.sock.sendto(packet, self.server_addr)

    def listen(self):
        while True:
            data, _ = self.sock.recvfrom(65535)
            msg = json.loads(data.decode())

            if msg.get("type") != "receive":
                continue

            # Extract transport fields (depends on your server forwarding format)
            t_id = msg.get("id")
            seq = msg.get("seq")
            total = msg.get("total")
            payload = msg.get("payload")

            if t_id is None:
                continue  # malformed packet

            if t_id not in self.partial_transports:
                self.partial_transports[t_id] = {
                    "total": total,
                    "chunks": {}
                }

            entry = self.partial_transports[t_id]
            entry["chunks"][seq] = base64.b64decode(payload)

            # Only assemble if ALL chunks are present
            if len(entry["chunks"]) == entry["total"]:
                try:
                    full_bytes = b''.join(
                        entry["chunks"][i]
                        for i in range(entry["total"])
                    )
                except KeyError:
                    # Missing chunk → shouldn't happen, but be safe
                    print("Missing chunk")
                    continue

                signal = np.frombuffer(full_bytes, dtype=np.float64)

                self.inbox.append(signal)

                del self.partial_transports[t_id]