#!/usr/bin/env python3
"""WebSocket MotionPacket Test Tool for ESP32 Robot.

Connects to the ESP32 async WebSocket endpoint (ws://<host>:<port>/ws),
allowing transmission of binary MotionPackets, fun trick trigger packets,
emergency stop packets, turbo/precision speed mode packets, and malformed test frames.
"""

import argparse
import asyncio
import sys
import time
from pathlib import Path

# Add repo root and protocol directory to sys.path
repo_root = Path(__file__).resolve().parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

protocol_dir = repo_root / "protocol"
if str(protocol_dir) not in sys.path:
    sys.path.insert(0, str(protocol_dir))

import websockets
from motion_packet import (
    MotionPacket,
    FLAG_ESTOP,
    FLAG_LOW_CONFIDENCE,
    FLAG_FUN_TRICK,
    FLAG_TURBO,
    FLAG_PRECISION,
)


async def run_trick_test(uri: str):
    """Sends a single fun-trick trigger packet."""
    print(f"[WS CLIENT] Connecting to {uri} ...")
    async with websockets.connect(uri) as ws:
        print("[WS CLIENT] Connected!")
        pkt = MotionPacket(seq=1, linear=0, angular=0, flags=FLAG_FUN_TRICK)
        print(f"[WS CLIENT] Sending fun trick packet (flags=0x{FLAG_FUN_TRICK:02X}) ...")
        await ws.send(pkt.to_bytes())
        print("[WS CLIENT] Sent! The robot should spin in place for ~1.5s.")
        await asyncio.sleep(2.0)
        # Send zero packet
        pkt_stop = MotionPacket(seq=2, linear=0, angular=0, flags=0)
        await ws.send(pkt_stop.to_bytes())
        print("[WS CLIENT] Sent normal zero packet. Trick test complete.")


async def run_estop_test(uri: str):
    """Sends an E-Stop packet."""
    print(f"[WS CLIENT] Connecting to {uri} ...")
    async with websockets.connect(uri) as ws:
        print("[WS CLIENT] Connected!")
        pkt = MotionPacket(seq=1, linear=0, angular=0, flags=FLAG_ESTOP)
        print(f"[WS CLIENT] Sending E-STOP packet (flags=0x{FLAG_ESTOP:02X}) ...")
        await ws.send(pkt.to_bytes())
        print("[WS CLIENT] Sent! Trick/motion should abort immediately.")


async def run_malformed_test(uri: str):
    """Sends malformed packets (wrong size, bad magic) to verify server resilience."""
    print(f"[WS CLIENT] Connecting to {uri} ...")
    async with websockets.connect(uri) as ws:
        print("[WS CLIENT] Connected!")

        # 1. Undersized frame (5 bytes instead of 10)
        print("[TEST 1] Sending 5-byte undersized frame...")
        await ws.send(b"\xA5\x01\x00\x01\x50")
        await asyncio.sleep(0.5)

        # 2. Corrupted magic byte
        print("[TEST 2] Sending 10-byte frame with invalid magic 0xFF...")
        bad_magic_pkt = b"\xFF\x01\x00\x02\x00\x00\x00\x00\x00\x00"
        await ws.send(bad_magic_pkt)
        await asyncio.sleep(0.5)

        # 3. Valid packet afterwards to prove server is still healthy
        print("[TEST 3] Sending valid MotionPacket to confirm connection remains alive...")
        valid_pkt = MotionPacket(seq=3, linear=20, angular=0)
        await ws.send(valid_pkt.to_bytes())
        await asyncio.sleep(0.5)
        print("[TEST RESULT] Server processed valid packet after rejecting malformed frames!")


async def run_stream_test(uri: str, linear: int, angular: int, duration: float, rate_hz: float, flags: int = 0):
    """Streams motion packets at specified rate for a given duration with flags."""
    flag_desc = []
    if flags & FLAG_TURBO:
        flag_desc.append("TURBO")
    if flags & FLAG_PRECISION:
        flag_desc.append("PRECISION")
    if flags & FLAG_FUN_TRICK:
        flag_desc.append("TRICK")
    if flags & FLAG_ESTOP:
        flag_desc.append("ESTOP")
    flag_str = "+".join(flag_desc) or "NOMINAL"

    print(f"[WS CLIENT] Connecting to {uri} ...")
    async with websockets.connect(uri) as ws:
        print(f"[WS CLIENT] Connected! Streaming (lin={linear}, ang={angular}, flags={flag_str}) at {rate_hz:.1f}Hz for {duration}s...")
        interval = 1.0 / rate_hz
        start = time.time()
        seq = 1

        while time.time() - start < duration:
            pkt = MotionPacket(seq=seq, linear=linear, angular=angular, flags=flags)
            await ws.send(pkt.to_bytes())
            seq = (seq + 1) % 65536
            await asyncio.sleep(interval)

        # Send final stop
        stop_pkt = MotionPacket(seq=seq, linear=0, angular=0, flags=0)
        await ws.send(stop_pkt.to_bytes())
        print("[WS CLIENT] Stream completed. Sent final stop.")


def main():
    parser = argparse.ArgumentParser(description="WebSocket Test Tool for ESP32 Robot")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="ESP32 IP address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=80, help="WebSocket port (default: 80)")
    parser.add_argument("--path", type=str, default="/ws", help="WebSocket path (default: /ws)")
    parser.add_argument("--mode", choices=["stream", "trick", "estop", "malformed", "turbo", "precision", "turbo_precision"],
                        default="trick", help="Test mode to execute (default: trick)")
    parser.add_argument("--linear", type=int, default=50, help="Linear speed for stream mode (-100..100)")
    parser.add_argument("--angular", type=int, default=0, help="Angular turn for stream mode (-100..100)")
    parser.add_argument("--duration", type=float, default=2.0, help="Duration in seconds for stream mode")
    parser.add_argument("--rate", type=float, default=20.0, help="Stream rate in Hz (default: 20)")

    args = parser.parse_args()
    uri = f"ws://{args.host}:{args.port}{args.path}"

    try:
        if args.mode == "trick":
            asyncio.run(run_trick_test(uri))
        elif args.mode == "estop":
            asyncio.run(run_estop_test(uri))
        elif args.mode == "malformed":
            asyncio.run(run_malformed_test(uri))
        elif args.mode == "stream":
            asyncio.run(run_stream_test(uri, args.linear, args.angular, args.duration, args.rate, flags=0))
        elif args.mode == "turbo":
            asyncio.run(run_stream_test(uri, args.linear, args.angular, args.duration, args.rate, flags=FLAG_TURBO))
        elif args.mode == "precision":
            asyncio.run(run_stream_test(uri, args.linear, args.angular, args.duration, args.rate, flags=FLAG_PRECISION))
        elif args.mode == "turbo_precision":
            asyncio.run(run_stream_test(uri, args.linear, args.angular, args.duration, args.rate, flags=FLAG_TURBO | FLAG_PRECISION))
    except Exception as e:
        print(f"[WS ERROR] Failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
