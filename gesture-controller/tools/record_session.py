#!/usr/bin/env python3
"""Record raw hand tracking session frames to JSON for offline tuning and replay."""

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any, Dict, List

src_dir = Path(__file__).resolve().parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from gesture.hand_tracker import HandTracker


def parse_args():
    parser = argparse.ArgumentParser(description="Record live camera gesture session to JSON.")
    parser.add_argument("--output", "-o", type=str, default="session_record.json", help="Output JSON path")
    parser.add_argument("--camera-index", type=int, default=0, help="Camera device index")
    parser.add_argument("--duration", type=float, default=0, help="Recording duration in seconds (0 = until 'q' or Ctrl+C)")
    parser.add_argument("--no-preview", action="store_true", help="Disable OpenCV preview window")
    return parser.parse_args()


def main():
    args = parse_args()

    try:
        import cv2
    except ImportError:
        print("[ERROR] OpenCV (cv2) is required to capture video.", file=sys.stderr)
        return 1

    try:
        tracker = HandTracker()
    except Exception as err:
        print(f"[ERROR] HandTracker initialization failed: {err}", file=sys.stderr)
        return 1

    cap = cv2.VideoCapture(args.camera_index)
    if not cap.isOpened():
        print(f"[ERROR] Could not open camera {args.camera_index}", file=sys.stderr)
        return 1

    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    print(f"[RECORD] Recording session to {args.output}. Press 'q' or Ctrl+C to stop.")
    recorded_frames: List[Dict[str, Any]] = []
    start_time = time.time()

    try:
        while cap.isOpened():
            ret, frame_bgr = cap.read()
            if not ret:
                time.sleep(0.01)
                continue

            now = time.time()
            if args.duration > 0 and (now - start_time) >= args.duration:
                break

            now_ms = int(now * 1000)
            h, w = frame_bgr.shape[:2]
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

            try:
                res = tracker.process(frame_rgb, timestamp_ms=now_ms)
                frame_data = {
                    "t_ms": now_ms,
                    "landmarks": res.landmarks,
                    "gesture": res.gesture,
                    "confidence": res.gesture_confidence,
                    "width": w,
                    "height": h,
                }
                recorded_frames.append(frame_data)
            except Exception as e:
                print(f"[WARN] Frame tracking failed: {e}")

            if not args.no_preview:
                preview = frame_bgr.copy()
                cv2.putText(
                    preview,
                    f"REC: {len(recorded_frames)} frames ({(now - start_time):.1f}s)",
                    (20, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 0, 255),
                    2,
                )
                cv2.imshow("Record Session", preview)
                if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                    break

    except KeyboardInterrupt:
        print("\n[RECORD] Interrupted by user.")
    finally:
        cap.release()
        tracker.close()
        if not args.no_preview:
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass

        out_path = Path(args.output).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps({"frames": recorded_frames}, indent=2), encoding="utf-8")
        print(f"[RECORD] Successfully saved {len(recorded_frames)} frames to {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
