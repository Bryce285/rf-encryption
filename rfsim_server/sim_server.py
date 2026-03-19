import socket
import json
import threading
import time
import random
import math


class RadioSimServer:
    def __init__(self, host="localhost", port=5000):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2 * 1024 * 1024)
        self.sock.bind((host, port))

        self.nodes = {}
        # node_id -> {
        #   "addr": (ip, port),
        #   "channel": str,
        #   "position": (x, y)
        # }

        self.channels = {}
        # channel_id -> set of node_ids currently on the channel

        # Simulation parameters
        self.latency = 0.01
        self.max_range = 1000
        self.burst_loss_prob = 0.03     # chance a burst starts
        self.burst_duration = (0.5, 2.0)  # min/max seconds a burst lasts
        self.active_bursts = {}        # (sender_id, receiver_id) -> burst_end_time

        self.pending_transports = {}   # transport_id -> {total, chunks}
        self.pending_lock = threading.Lock()

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

        elif msg_type == "transport":
            self.buffer_transport(msg)

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

        self.channels.setdefault(channel, set())

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

        self.channels.setdefault(new_channel, set())

        print(f"{node_id} switched to {new_channel}")

    def distance(self, pos1, pos2):
        dx = pos1[0] - pos2[0]
        dy = pos1[1] - pos2[1]
        print("Calculated distance: " + str(math.sqrt(dx * dx + dy * dy)))
        return math.sqrt(dx * dx + dy * dy)

    # ============================
    # Transport Chunk Buffering
    # ============================

    def buffer_transport(self, msg):
        """Buffer incoming transport chunks. Once all chunks of a signal
        arrive, hand the complete set to handle_transmission."""
        t_id = msg.get("id")
        seq = msg.get("seq")
        total = msg.get("total")

        with self.pending_lock:
            if t_id not in self.pending_transports:
                self.pending_transports[t_id] = {
                    "total": total,
                    "chunks": {}
                }

            entry = self.pending_transports[t_id]
            entry["chunks"][seq] = msg

            if len(entry["chunks"]) < total:
                return  # still waiting for more chunks

            ordered_chunks = [entry["chunks"][i] for i in range(total)]
            del self.pending_transports[t_id]

        # All chunks received — process the complete signal
        self.handle_transmission(ordered_chunks)

    # ============================
    # Transmission Handling
    # ============================

    def handle_transmission(self, chunks):
        """Simulate transmission of a complete signal (all transport chunks).
        Loss and collision decisions are per-signal, not per-chunk."""
        sender_id = chunks[0]["node_id"]

        if sender_id not in self.nodes:
            return

        sender_info = self.nodes[sender_id]
        channel_id = sender_info["channel"]

        print(f"{sender_id} transmitting on {channel_id}")

        # Deliver to receivers
        for node_id, node in self.nodes.items():
            if node_id == sender_id:
                continue

            if node["channel"] != channel_id:
                continue

            # Range check
            distance = self.distance(sender_info["position"], node["position"])
            max_d = self.max_range

            # Normalize distance (0 → 1)
            d_norm = distance / max_d

            # Loss increases with distance (quadratic works well)
            if distance == 0:
                loss_prob = 0
            else:
                loss_prob = self.burst_loss_prob + (d_norm ** 2) * 0.5

            # Burst loss — applied per (sender, receiver) pair
            burst_key = (sender_id, node_id)
            now = time.time()

            if burst_key in self.active_bursts:
                if now < self.active_bursts[burst_key]:
                    print("Dropped (burst)")
                    continue
                else:
                    del self.active_bursts[burst_key]

            # Possibly start a new burst
            if random.random() < self.burst_loss_prob:
                duration = random.uniform(*self.burst_duration)
                self.active_bursts[burst_key] = now + duration
                print(f"Starting burst loss: {duration:.2f}s")
                continue

            if random.random() < loss_prob:
                print("Dropped (distance)")
                continue

            # Latency (with optional jitter)
            time.sleep(self.latency + random.uniform(0, 0.01))

            # Forward ALL chunks of this signal
            for chunk in chunks:
                packet = json.dumps({
                    "type": "receive",
                    "from": sender_id,
                    "id": chunk.get("id"),
                    "seq": chunk.get("seq"),
                    "total": chunk.get("total"),
                    "payload": chunk["payload"]
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