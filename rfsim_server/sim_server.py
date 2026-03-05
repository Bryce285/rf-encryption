import socket
import json
import threading
import time
import random
import math

# TODO - add some features for more realism

class RadioSimServer:
    def __init__(self, host="localhost", port=5000):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((host, port))

        self.nodes = {}
        # node_id -> {
        #   "addr": (ip, port),
        #   "channel": str,
        #   "position": (x, y)
        # }

        self.channels = {}
        # channel_id -> {
        #   "transmitting": {node_id: end_time},
        #   "lock": threading.Lock()
        # }

        # Simulation parameters
        self.packet_loss = 0.05
        self.latency = 0.05
        self.max_range = 100
        self.data_rate = 1000.0  # bytes per second

    # ============================
    # Server Main Loop
    # ============================

    def start(self):
        print("RadioSim server running...")
        while True:
            data, addr = self.sock.recvfrom(65535)
            try:
                message = json.loads(data.decode())
            except:
                continue

            threading.Thread(
                target=self.handle_message,
                args=(message, addr),
                daemon=True
            ).start()

    # ============================
    # Message Dispatcher
    # ============================

    def handle_message(self, msg, addr):
        msg_type = msg.get("type")

        if msg_type == "register":
            self.register_node(msg, addr)

        elif msg_type == "switch_channel":
            self.switch_channel(msg)

        elif msg_type == "transmit":
            self.handle_transmission(msg)

    # ============================
    # Node Registration
    # ============================

    def register_node(self, msg, addr):
        node_id = msg["node_id"]
        channel = msg["channel"]
        position = tuple(msg["position"])

        self.nodes[node_id] = {
            "addr": addr,
            "channel": channel,
            "position": position
        }

        self.channels.setdefault(
            channel,
            {"transmitting": {}, "lock": threading.Lock()}
        )

        print(f"{node_id} registered on {channel}")

    # ============================
    # Channel Switching
    # ============================

    def switch_channel(self, msg):
        node_id = msg["node_id"]
        new_channel = msg["channel"]

        if node_id not in self.nodes:
            return

        self.nodes[node_id]["channel"] = new_channel

        self.channels.setdefault(
            new_channel,
            {"transmitting": {}, "lock": threading.Lock()}
        )

        print(f"{node_id} switched to {new_channel}")

    # ============================
    # Transmission Handling
    # ============================

    def handle_transmission(self, msg):
        sender_id = msg["node_id"]
        payload = msg["payload"]

        if sender_id not in self.nodes:
            return

        sender_info = self.nodes[sender_id]
        channel_id = sender_info["channel"]

        channel = self.channels[channel_id]

        tx_time = len(payload.encode()) / self.data_rate
        now = time.time()

        with channel["lock"]:
            # Remove expired transmissions
            expired = [
                node for node, end_time in channel["transmitting"].items()
                if end_time <= now
            ]
            for node in expired:
                del channel["transmitting"][node]

            # Check for other active transmitters
            other_tx = [
                node for node in channel["transmitting"]
                if node != sender_id
            ]

            if other_tx:
                print(f"Collision: {sender_id} with {other_tx}")
                return

            # Register this transmission
            channel["transmitting"][sender_id] = now + tx_time

        print(f"{sender_id} transmitting on {channel_id}")

        # Simulate transmission duration
        time.sleep(tx_time)

        # Deliver to receivers
        for node_id, node in self.nodes.items():
            if node_id == sender_id:
                continue

            if node["channel"] != channel_id:
                continue

            # Range check
            if not self.in_range(sender_info["position"], node["position"]):
                continue

            # Packet loss
            if random.random() < self.packet_loss:
                print("Packet lost due to noise")
                continue

            # Latency
            time.sleep(self.latency)

            packet = json.dumps({
                "type": "receive",
                "from": sender_id,
                "payload": payload
            }).encode()

            self.sock.sendto(packet, node["addr"])

        print(f"{sender_id} transmission complete")

    # ============================
    # Range Calculation
    # ============================

    def in_range(self, pos1, pos2):
        dx = pos1[0] - pos2[0]
        dy = pos1[1] - pos2[1]
        distance = math.sqrt(dx * dx + dy * dy)
        return distance <= self.max_range

if __name__ == "__main__":
    server = RadioSimServer()
    server.start()