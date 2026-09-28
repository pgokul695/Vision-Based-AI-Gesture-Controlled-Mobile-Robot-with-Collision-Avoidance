#!/usr/bin/env python3
"""Replay recorded session frames through the gesture pipeline to tune parameters."""

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, List

src_dir = Path(__file__).resolve().parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from gesture.pipeline import GesturePipeline


def parse_args():
    parser = argparse.ArgumentParser(description="Replay recorded session frames through GesturePipeline.")
    parser.add_argument("input", type=str, help="Path to recorded session JSON file")
    parser.add_argument("--config", "-c", type=str, default=None, help="Custom gesture-config.json to test")
    parser.add_argument("--mode", type=str, choices=["classic", "joystick"], default=None, help="Override control mode")
    parser.add_argument("--sensitivity", type=float, default=None, help="Override sensitivity")
    parser.add_argument("--plot", action="store_true", help="Plot linear and angular outputs using matplotlib")
    return parser.parse_args()


def main():
    args = parse_args()
    input_path = Path(args.input).resolve()
    if not input_path.exists():
        print(f"[ERROR] Input file not found: {input_path}", file=sys.stderr)
        return 1

    data = json.loads(input_path.read_text(encoding="utf-8"))
    frames: List[Dict[str, Any]] = data.get("frames", [])
    if not frames and isinstance(data, list):
        frames = data

    if not frames:
        print(f"[ERROR] No frames found in {input_path}", file=sys.stderr)
        return 1

    config = None
    if args.config:
        config_path = Path(args.config).resolve()
        if config_path.is_file():
            config = json.loads(config_path.read_text(encoding="utf-8"))

    pipeline = GesturePipeline(config=config)
    if args.mode:
        pipeline.set_control_mode(args.mode)
    if args.sensitivity is not None:
        pipeline.set_sensitivity(args.sensitivity)

    print(f"=== Replaying {len(frames)} frames through GesturePipeline ===")
    print(f"Mode: {pipeline.control_mode} | Sensitivity: {pipeline.sensitivity} | Smoothing: {pipeline.smoothing_preset}")

    results = []
    state_counts: Dict[str, int] = {}
    time_series_t = []
    time_series_lin = []
    time_series_ang = []
    time_series_pre_lin = []
    time_series_pre_ang = []

    for idx, f in enumerate(frames):
        t_ms = f.get("t_ms", idx * 50)
        res = pipeline.step(f, t_ms)
        results.append(res)

        st = res["debug"]["state"]
        state_counts[st] = state_counts.get(st, 0) + 1

        time_series_t.append(t_ms / 1000.0)
        time_series_lin.append(res["linear"])
        time_series_ang.append(res["angular"])
        time_series_pre_lin.append(res["debug"]["pre_ramp_linear"])
        time_series_pre_ang.append(res["debug"]["pre_ramp_angular"])

    # Summary Statistics
    total_frames = len(frames)
    duration_s = (time_series_t[-1] - time_series_t[0]) if len(time_series_t) > 1 else 0.0

    print("\n--- Summary Statistics ---")
    print(f"Total Frames:  {total_frames}")
    print(f"Duration:      {duration_s:.2f} s")
    print("State Distribution:")
    for st, count in sorted(state_counts.items()):
        pct = (count / total_frames) * 100.0
        print(f"  {st:10s}: {count:5d} frames ({pct:5.1f}%)")

    max_lin = max(time_series_lin) if time_series_lin else 0
    min_lin = min(time_series_lin) if time_series_lin else 0
    max_ang = max(time_series_ang) if time_series_ang else 0
    min_ang = min(time_series_ang) if time_series_ang else 0
    print(f"Linear range:  [{min_lin:+4d}, {max_lin:+4d}] %")
    print(f"Angular range: [{min_ang:+4d}, {max_ang:+4d}] %")

    # Optional plotting
    if args.plot:
        try:
            import matplotlib.pyplot as plt

            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
            ax1.plot(time_series_t, time_series_pre_lin, "g--", alpha=0.5, label="Pre-ramp Linear")
            ax1.plot(time_series_t, time_series_lin, "g-", linewidth=2, label="Output Linear")
            ax1.set_ylabel("Linear (%)")
            ax1.grid(True)
            ax1.legend(loc="upper right")

            ax2.plot(time_series_t, time_series_pre_ang, "b--", alpha=0.5, label="Pre-ramp Angular")
            ax2.plot(time_series_t, time_series_ang, "b-", linewidth=2, label="Output Angular")
            ax2.set_xlabel("Time (s)")
            ax2.set_ylabel("Angular (%)")
            ax2.grid(True)
            ax2.legend(loc="upper right")

            plt.suptitle(f"Gesture Replay: {input_path.name} ({pipeline.control_mode})")
            plt.tight_layout()
            plt.show()
        except ImportError:
            print("\n[NOTE] matplotlib is not installed. To see visual plots, install it with 'pip install matplotlib'.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
