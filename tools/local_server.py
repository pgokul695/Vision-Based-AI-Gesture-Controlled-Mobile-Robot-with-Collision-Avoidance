#!/usr/bin/env python3
"""Local development HTTP and WebSocket server for the Robot Web App HUD.

Serves the webapp on localhost and accepts WebSocket connections at /ws,
parsing incoming 10-byte binary MotionPackets with ASCII telemetry display.

Usage:
  python tools/local_server.py [--port 8080] [--host 127.0.0.1]
"""

import argparse
from pathlib import Path
import socket
import sys
import time

repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from protocol.motion_packet import MotionPacket, MOTION_PACKET_MAGIC, MOTION_PACKET_VERSION

try:
    from aiohttp import web, WSMsgType
except ImportError:
    print("[ERROR] aiohttp is required. Install via 'pip install aiohttp'.", file=sys.stderr)
    sys.exit(1)


def render_ascii_bar(value: int, bar_width: int = 10) -> str:
    clamped = max(-100, min(100, value))
    half_chars = round((abs(clamped) / 100.0) * bar_width)
    if clamped < 0:
        left_fill = "<" * half_chars
        left_pad = " " * (bar_width - half_chars)
        right_pad = " " * bar_width
        return f"[{left_pad}{left_fill}|{right_pad}]"
    elif clamped > 0:
        left_pad = " " * bar_width
        right_fill = ">" * half_chars
        right_pad = " " * (bar_width - half_chars)
        return f"[{left_pad}|{right_fill}{right_pad}]"
    else:
        left_pad = " " * bar_width
        right_pad = " " * bar_width
        return f"[{left_pad}|{right_pad}]"


class LocalRobotServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8080, udp_forward: str = None):
        self.host = host
        self.port = port
        self.udp_forward = udp_forward
        self.udp_sock = None
        if udp_forward:
            u_host, u_port = udp_forward.split(":")
            self.udp_target = (u_host, int(u_port))
            self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.webapp_dir = repo_root / "webapp"
        self.app = web.Application()
        self._setup_routes()

        self.packet_count = 0
        self.last_print_time = 0.0

    def _setup_routes(self):
        self.app.router.add_get("/", self.index_handler)
        self.app.router.add_get("/ws", self.websocket_handler)
        # Static files fallback
        self.app.router.add_static("/", path=str(self.webapp_dir), show_index=False)

    async def index_handler(self, request):
        index_file = self.webapp_dir / "index.html"
        return web.FileResponse(index_file)

    async def websocket_handler(self, request):
        ws = web.WebSocketResponse(heartbeat=10.0)
        await ws.prepare(request)
        peer = request.remote or "client"
        print(f"\n[WS CONNECTED] Client connected from {peer}")

        try:
            async for msg in ws:
                if msg.type == WSMsgType.BINARY:
                    self.packet_count += 1
                    data = msg.data
                    if len(data) != 10:
                        print(f"[WS ERROR] Packet size {len(data)} != 10 bytes")
                        continue

                    try:
                        pkt = MotionPacket.from_bytes(data)
                    except ValueError as err:
                        print(f"[WS ERROR] Protocol mismatch: {err}")
                        continue

                    if self.udp_sock:
                        self.udp_sock.sendto(data, self.udp_target)

                    now = time.time()
                    # Throttle console prints to ~10 Hz so terminal stays legible
                    if (now - self.last_print_time) >= 0.1:
                        flags_list = []
                        if pkt.is_estop:
                            flags_list.append("\033[91m[E-STOP]\033[0m")
                        if pkt.is_turbo:
                            flags_list.append("\033[93m[TURBO]\033[0m")
                        if pkt.is_precision:
                            flags_list.append("\033[94m[PREC]\033[0m")
                        if pkt.is_fun_trick:
                            flags_list.append("\033[95m[TRICK]\033[0m")
                        if pkt.is_low_confidence:
                            flags_list.append("\033[90m[DISARM]\033[0m")
                        if not flags_list:
                            flags_list.append("\033[92m[ACTIVE]\033[0m")

                        flags_str = " ".join(flags_list)
                        lin_bar = render_ascii_bar(pkt.linear, bar_width=8)
                        ang_bar = render_ascii_bar(pkt.angular, bar_width=8)

                        sys.stdout.write(
                            f"\r#{pkt.seq:05d} | "
                            f"Lin {pkt.linear:+4d}% {lin_bar} | "
                            f"Ang {pkt.angular:+4d}% {ang_bar} | "
                            f"{flags_str:30s}"
                        )
                        sys.stdout.flush()
                        self.last_print_time = now

                elif msg.type == WSMsgType.ERROR:
                    print(f"[WS ERROR] WebSocket exception: {ws.exception()}")

        finally:
            print(f"\n[WS DISCONNECTED] Client disconnected ({self.packet_count} packets received).")

        return ws

    def start(self):
        print("=" * 65)
        print("  ESP32 ROBOT WEB APP - LOCAL SERVER")
        print("=" * 65)
        print(f"  Web HUD URL:      http://{self.host}:{self.port}/")
        print(f"  WebSocket URL:    ws://{self.host}:{self.port}/ws")
        print(f"  Serving Directory: {self.webapp_dir}")
        if self.udp_forward:
            print(f"  Forwarding UDP:   {self.udp_target}")
        print("=" * 65)
        print("  Open http://localhost:" + str(self.port) + "/ in your browser.")
        print("  Press Ctrl+C to stop the server.\n")

        web.run_app(self.app, host=self.host, port=self.port, print=None)


def main():
    parser = argparse.ArgumentParser(description="Run local Web App and WebSocket server.")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind (default: 8080)")
    parser.add_argument("--udp-forward", type=str, default=None, help="Forward UDP to host:port (e.g. 127.0.0.1:5005)")
    args = parser.parse_args()

    server = LocalRobotServer(host=args.host, port=args.port, udp_forward=args.udp_forward)
    server.start()


if __name__ == "__main__":
    main()
