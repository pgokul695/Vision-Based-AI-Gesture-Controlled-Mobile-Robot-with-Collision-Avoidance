#!/usr/bin/env python3
"""Mock UDP receiver simulating ESP32 robot firmware.

Listens for 10-byte binary MotionPackets, verifies protocol integrity,
tracks sequence continuity, and displays an ASCII visualization of commanded motion.
"""

import argparse
import socket
import sys
import time
from pathlib import Path

# Add repo root to import protocol module
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

# Also support when run from within gesture-controller/tools/
repo_root_alt = Path(__file__).resolve().parent.parent.parent
if str(repo_root_alt) not in sys.path:
    sys.path.insert(0, str(repo_root_alt))

from protocol.motion_packet import MotionPacket, MOTION_PACKET_MAGIC, MOTION_PACKET_VERSION


def render_ascii_bar(value: int, bar_width: int = 10) -> str:
    """Renders a bidirectional ASCII meter for values between -100 and +100.

    Center is '|'. Negative fills left with '<', positive fills right with '>'.
    Example:
      -50 -> [<<<<<     |          ]
       +70 -> [          |>>>>>>>   ]
         0 -> [          |          ]
    """
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


def run_mock_receiver(host: str, port: int, verbose: bool = False):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host, port))
    print(f"============================================================")
    print(f"  Mock ESP32 Motion Receiver listening on {host}:{port}")
    print(f"  Expecting 10-byte binary MotionPackets (Magic 0x{MOTION_PACKET_MAGIC:02X}, V{MOTION_PACKET_VERSION})")
    print(f"  Press Ctrl+C to exit.")
    print(f"============================================================\n")

    expected_seq = None
    packet_count = 0
    dropped_count = 0
    last_print_time = 0.0

    try:
        while True:
            data, addr = sock.recvfrom(1024)
            recv_time = time.time()
            packet_count += 1

            # Validate packet size
            if len(data) != 10:
                print(f"[RECV ERROR] Invalid packet size: received {len(data)} bytes from {addr} (expected 10)")
                continue

            try:
                pkt = MotionPacket.from_bytes(data)
            except ValueError as err:
                print(f"[RECV ERROR] Packet validation failure from {addr}: {err}")
                continue

            # Sequence tracking & drop detection
            seq_gap_warning = ""
            if expected_seq is not None:
                if pkt.seq != expected_seq:
                    diff = (pkt.seq - expected_seq) % 65536
                    dropped_count += diff
                    seq_gap_warning = f" ! GAP: missed {diff} (exp {expected_seq}, got {pkt.seq}) !"
            expected_seq = (pkt.seq + 1) % 65536

            # Format status flags
            flag_strs = []
            if pkt.is_estop:
                flag_strs.append("[E-STOP]")
            if pkt.is_low_confidence:
                flag_strs.append("[LOW_CONF]")
            if not flag_strs:
                flag_strs.append("[NOMINAL]")
            flags_display = " ".join(flag_strs)

            linear_bar = render_ascii_bar(pkt.linear, bar_width=10)
            angular_bar = render_ascii_bar(pkt.angular, bar_width=10)

            print(
                f"#{pkt.seq:05d} | "
                f"Lin {pkt.linear:+4d}% {linear_bar} | "
                f"Ang {pkt.angular:+4d}% {angular_bar} | "
                f"{flags_display:18s}"
                f"{seq_gap_warning}",
                flush=True
            )

    except KeyboardInterrupt:
        print("\n[MOCK RECEIVER] Shutting down...", flush=True)
    finally:
        sock.close()
        print(f"Summary: {packet_count} packets processed, {dropped_count} sequence gaps detected.", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Mock ESP32 UDP Receiver for MotionPackets")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Binding IP address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8888, help="Listening UDP port (default: 8888)")
    parser.add_argument("--verbose", action="store_true", help="Print raw bytes")
    args = parser.parse_args()

    run_mock_receiver(args.host, args.port, args.verbose)


if __name__ == "__main__":
    main()
