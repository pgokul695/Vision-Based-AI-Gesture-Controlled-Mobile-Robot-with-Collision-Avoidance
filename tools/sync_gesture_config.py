#!/usr/bin/env python3
"""Synchronize or verify byte-identical gesture-config.json between repo root and webapp.

Usage:
  python tools/sync_gesture_config.py         # Copies root config to webapp/gesture-config.json
  python tools/sync_gesture_config.py --check # Verifies files are byte-identical (exit 0 on match, 1 on mismatch)
"""

import argparse
from pathlib import Path
import sys

def main() -> int:
    parser = argparse.ArgumentParser(description="Sync or check gesture-config.json across root and webapp.")
    parser.add_argument("--check", action="store_true", help="Assert files are byte-identical without modifying.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    src_config = repo_root / "gesture-config.json"
    dst_config = repo_root / "webapp" / "gesture-config.json"

    if not src_config.exists():
        print(f"Error: Source config not found at {src_config}", file=sys.stderr)
        return 1

    src_bytes = src_config.read_bytes()

    if args.check:
        if not dst_config.exists():
            print(f"Error: Destination config does not exist at {dst_config}", file=sys.stderr)
            return 1
        dst_bytes = dst_config.read_bytes()
        if src_bytes != dst_bytes:
            print("Error: gesture-config.json and webapp/gesture-config.json are not byte-identical!", file=sys.stderr)
            return 1
        print("OK: gesture-config.json and webapp/gesture-config.json are byte-identical.")
        return 0

    # Sync mode: copy src to dst
    dst_config.parent.mkdir(parents=True, exist_ok=True)
    dst_config.write_bytes(src_bytes)
    print(f"Synced {src_config} -> {dst_config} ({len(src_bytes)} bytes)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
