"""Main application loop for vision-based AI gesture controller.

Captures webcam frames in a dedicated thread, runs MediaPipe GestureRecognizer,
evaluates pure GesturePipeline, streams 10-byte binary UDP datagrams to the robot,
and renders an interactive HUD with real-time controls.
"""

import argparse
import math
from pathlib import Path
import sys
import threading
import time
from typing import Any, Dict, Optional, Tuple

# Resolve imports for local modules and shared protocol
src_dir = Path(__file__).resolve().parent
repo_root = src_dir.parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from gesture.hand_tracker import HandTracker, HandTrackingResult
from gesture.pipeline import GesturePipeline
from network.udp_sender import UdpSender


class CameraCaptureThread:
    """Dedicated background capture thread that always keeps only the latest frame."""

    def __init__(self, camera_index: int = 0):
        try:
            import cv2
        except ImportError as e:
            raise ImportError("OpenCV (cv2) is required.") from e

        self.cv2 = cv2
        self.camera_index = camera_index
        self.cap = cv2.VideoCapture(camera_index)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.running = False
        self.lock = threading.Lock()
        self.latest_frame = None
        self.frame_timestamp: float = 0.0
        self.thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if not self.cap.isOpened():
            raise RuntimeError(f"Could not open camera device at index {self.camera_index}")
        self.running = True
        self.thread = threading.Thread(target=self._capture_worker, daemon=True)
        self.thread.start()

    def _capture_worker(self) -> None:
        while self.running and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                now = time.time()
                with self.lock:
                    self.latest_frame = frame
                    self.frame_timestamp = now
            else:
                time.sleep(0.01)

    def read_latest(self) -> Tuple[Optional[Any], float]:
        with self.lock:
            if self.latest_frame is None:
                return None, 0.0
            return self.latest_frame.copy(), self.frame_timestamp

    def stop(self) -> None:
        self.running = False
        if self.thread is not None:
            self.thread.join(timeout=1.0)
        if self.cap is not None:
            self.cap.release()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Vision-Based AI Gesture Controller (Ergonomics Upgrade)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Target robot IP / hostname")
    parser.add_argument("--port", type=int, default=5005, help="Target robot UDP port")
    parser.add_argument("--camera-index", type=int, default=0, help="Webcam device index")
    parser.add_argument("--rate", type=float, default=20.0, help="UDP transmission rate in Hz")
    parser.add_argument("--model-path", type=str, default=None, help="Path to gesture_recognizer.task model file")
    parser.add_argument("--mode", type=str, choices=["classic", "joystick"], default=None, help="Control mode")
    parser.add_argument("--sensitivity", type=float, default=None, help="Sensitivity multiplier")
    parser.add_argument("--smoothing", type=str, choices=["low", "medium", "high"], default=None, help="Smoothing preset")
    parser.add_argument("--no-mirror", action="store_true", help="Disable mirror preview display")
    parser.add_argument("--trace", type=str, default=None, help="Path to write per-frame diagnostic CSV trace")
    parser.add_argument("--debug", action="store_true", help="Enable verbose debug readout")
    parser.add_argument("--no-gui", action="store_true", help="Run in headless mode without cv2.imshow GUI")
    return parser.parse_args()


def draw_hud(
    frame_disp,
    step_result: Dict[str, Any],
    tracking: Optional[HandTrackingResult],
    pipeline: GesturePipeline,
    fps: float,
    latency_ms: float,
    show_debug: bool,
):
    """Draws on-screen debug HUD displaying gesture status, state colors, and control overlay."""
    try:
        import cv2
    except ImportError:
        return

    h, w = frame_disp.shape[:2]
    debug = step_result["debug"]
    state = debug["state"]
    linear = step_result["linear"]
    angular = step_result["angular"]
    flags = step_result["flags"]
    latched_mode = debug["latched_mode"]
    anchor = debug["anchor"]
    smoothed_hand = debug["smoothed_hand"]
    control_mode = pipeline.control_mode
    is_mirrored = pipeline.mirror_preview

    # Helper to map user-space pixel X to display pixel X
    def to_disp_x(user_x: float) -> int:
        if is_mirrored:
            return int(user_x)
        else:
            return int(w - user_x)

    # State colors (BGR)
    state_colors = {
        "IDLE": (180, 180, 180),       # Gray
        "ENGAGING": (0, 215, 255),     # Yellow / Amber
        "DRIVING": (0, 255, 0),        # Green
        "GRACE": (0, 140, 255),        # Orange
        "ESTOP": (0, 0, 255),          # Red
    }
    banner_color = state_colors.get(state, (200, 200, 200))

    # 1. Draw Mode Overlays
    if control_mode == "joystick" and anchor is not None:
        anc_disp_x = to_disp_x(anchor[0])
        anc_disp_y = int(anchor[1])
        scale = debug.get("smoothed_scale") or 80.0
        fs_ratio = float(pipeline.map_cfg.get("joystick_full_scale", 1.2))
        dz_ratio = float(pipeline.map_cfg.get("joystick_deadzone", 0.15))

        # Anchor dot & ring
        cv2.circle(frame_disp, (anc_disp_x, anc_disp_y), 6, (0, 255, 255), -1)
        cv2.circle(frame_disp, (anc_disp_x, anc_disp_y), 10, (0, 255, 255), 1)

        # Deadzone circle
        cv2.circle(frame_disp, (anc_disp_x, anc_disp_y), int(dz_ratio * scale), (100, 100, 100), 1)

        # Full-scale circle
        cv2.circle(frame_disp, (anc_disp_x, anc_disp_y), int(fs_ratio * scale), (255, 255, 0), 2)

        # Vector line to smoothed hand
        if smoothed_hand is not None:
            hand_disp_x = to_disp_x(smoothed_hand[0])
            hand_disp_y = int(smoothed_hand[1])
            cv2.line(frame_disp, (anc_disp_x, anc_disp_y), (hand_disp_x, hand_disp_y), (0, 255, 0), 2)

    elif control_mode == "classic":
        throttle_mode = pipeline.map_cfg.get("throttle_neutral", "anchor")
        if throttle_mode == "frame_center":
            neutral_y = int(0.5 * h)
            cv2.line(frame_disp, (0, neutral_y), (w, neutral_y), (0, 215, 255), 1, cv2.LINE_AA)
            cv2.putText(
                frame_disp,
                "NEUTRAL ZONE",
                (15, max(15, neutral_y - 6)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                (0, 215, 255),
                1,
            )
        elif anchor is not None and state != "IDLE":
            neutral_y = int(anchor[1])
            cv2.line(frame_disp, (0, neutral_y), (w, neutral_y), (0, 215, 255), 1, cv2.LINE_AA)
            cv2.putText(
                frame_disp,
                "ANCHOR NEUTRAL",
                (15, max(15, neutral_y - 6)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                (0, 215, 255),
                1,
            )
            anc_disp_x = to_disp_x(anchor[0])
            cv2.circle(frame_disp, (anc_disp_x, neutral_y), 4, (0, 215, 255), -1)
            if smoothed_hand is not None:
                hand_disp_x = to_disp_x(smoothed_hand[0])
                hand_disp_y = int(smoothed_hand[1])
                cv2.line(frame_disp, (anc_disp_x, neutral_y), (hand_disp_x, hand_disp_y), banner_color, 2)

        # Tilt gauge in top right
        gauge_cx, gauge_cy = w - 80, 70
        cv2.circle(frame_disp, (gauge_cx, gauge_cy), 35, (60, 60, 60), 2)
        tilt_deg = debug.get("smoothed_tilt") or 0.0
        neutral_tilt = debug.get("neutral_tilt") or 0.0
        eff_tilt = tilt_deg - neutral_tilt

        # Draw tilt needle
        tilt_rad = math.radians(eff_tilt)
        needle_len = 30
        needle_dx = int(needle_len * math.sin(tilt_rad))
        needle_dy = int(-needle_len * math.cos(tilt_rad))
        # Needle direction in display coordinates
        needle_screen_dx = needle_dx if is_mirrored else -needle_dx
        cv2.line(frame_disp, (gauge_cx, gauge_cy), (gauge_cx + needle_screen_dx, gauge_cy + needle_dy), (0, 255, 255), 2)
        cv2.putText(
            frame_disp,
            f"TILT: {eff_tilt:+.1f} deg",
            (gauge_cx - 50, gauge_cy + 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            (200, 200, 200),
            1,
        )

    # Smoothed hand position dot
    if smoothed_hand is not None:
        sh_disp_x = to_disp_x(smoothed_hand[0])
        sh_disp_y = int(smoothed_hand[1])
        cv2.circle(frame_disp, (sh_disp_x, sh_disp_y), 7, banner_color, -1)

    # 2. Status HUD Panel
    overlay = frame_disp.copy()
    cv2.rectangle(overlay, (10, 10), (420, 180), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.75, frame_disp, 0.25, 0, frame_disp)

    # Header with state color
    status_text = f"STATE: [{state}]"
    cv2.putText(frame_disp, status_text, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.65, banner_color, 2)

    gesture_label = tracking.gesture if (tracking and tracking.gesture) else "None"
    conf_val = (tracking.gesture_confidence * 100.0) if (tracking and tracking.gesture_confidence) else 0.0
    cv2.putText(
        frame_disp,
        f"Gesture: {gesture_label} ({conf_val:.0f}%) | Mode: {latched_mode}",
        (20, 65),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (255, 255, 255),
        1,
    )

    cv2.putText(
        frame_disp,
        f"Linear:  {linear:+4d}%   |   Angular: {angular:+4d}%",
        (20, 95),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (0, 255, 255),
        2,
    )

    cv2.putText(
        frame_disp,
        f"Control: {control_mode.upper()}  |  Sens: {pipeline.sensitivity:.1f}x  |  {pipeline.smoothing_preset}",
        (20, 125),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.48,
        (200, 200, 200),
        1,
    )

    debug_str = f"FPS: {fps:.1f}"
    if show_debug:
        debug_str += f" | Latency: {latency_ms:.1f}ms | Mirror: {is_mirrored}"
    debug_str += " | [h]elp / [q]uit"

    cv2.putText(
        frame_disp,
        debug_str,
        (20, 155),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.42,
        (150, 150, 150),
        1,
    )


def print_active_settings(pipeline: GesturePipeline, host: str, port: int, rate: float):
    print("\n" + "=" * 60)
    print(" VISION-BASED AI GESTURE CONTROLLER (ERGONOMICS UPGRADE)")
    print("=" * 60)
    print(f" Target Robot UDP:      {host}:{port}")
    print(f" Transmission Rate:     {rate} Hz")
    print(f" Active Control Mode:   {pipeline.control_mode.upper()}")
    print(f" Sensitivity:           {pipeline.sensitivity:.1f}x")
    print(f" Smoothing Preset:      {pipeline.smoothing_preset}")
    print(f" Mirror Preview:        {pipeline.mirror_preview}")
    print("-" * 60)
    print(" Hotkeys in Preview Window:")
    print("   [m] : Toggle preview mirroring")
    print("   [j] : Toggle mode (Classic <-> Joystick)")
    print("   [+] : Increase sensitivity (+0.1)")
    print("   [-] : Decrease sensitivity (-0.1)")
    print("   [d] : Toggle debug telemetry (FPS & Latency)")
    print("   [q] : Quit controller")
    print("=" * 60 + "\n")


def main():
    args = parse_args()

    target_host = args.host.strip()
    target_port = args.port
    if "://" in target_host:
        from urllib.parse import urlparse
        parsed = urlparse(target_host)
        target_host = parsed.hostname or target_host
        if parsed.port:
            target_port = parsed.port
    else:
        target_host = target_host.rstrip("/").split(":")[0]

    pipeline = GesturePipeline()
    if args.mode:
        pipeline.set_control_mode(args.mode)
    if args.sensitivity is not None:
        pipeline.set_sensitivity(args.sensitivity)
    if args.smoothing:
        pipeline.set_smoothing_preset(args.smoothing)
    if args.no_mirror:
        pipeline.set_mirror_preview(False)

    print_active_settings(pipeline, target_host, target_port, args.rate)

    try:
        tracker = HandTracker(model_path=args.model_path)
    except Exception as err:
        print(f"\n[ERROR] HandTracker initialization failed: {err}\n", file=sys.stderr)
        sys.exit(1)

    try:
        import cv2
    except ImportError:
        print("[ERROR] OpenCV (cv2) is required.", file=sys.stderr)
        sys.exit(1)

    sender = UdpSender(host=target_host, port=target_port)
    sender.start()

    try:
        cam_thread = CameraCaptureThread(camera_index=args.camera_index)
        cam_thread.start()
    except Exception as e:
        print(f"[ERROR] Camera initialization error: {e}", file=sys.stderr)
        sender.close()
        tracker.close()
        sys.exit(1)

    udp_interval = 1.0 / args.rate
    last_udp_send_time = 0.0
    fps = 0.0
    frame_count = 0
    fps_start_time = time.time()
    show_debug = args.debug

    # Initialize CSV trace file if --trace specified
    trace_file = None
    trace_writer = None
    if args.trace:
        import csv
        trace_path = Path(args.trace).resolve()
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        trace_file = open(trace_path, "w", newline="", encoding="utf-8")
        trace_writer = csv.writer(trace_file)
        trace_writer.writerow([
            "t_ms", "gesture", "confidence", "state", "has_hand",
            "palm_x", "palm_y", "scale", "tilt", "extension",
            "anchor_x", "anchor_y",
            "lin_raw_disp", "lin_norm", "lin_after_deadzone", "lin_after_expo", "lin_target", "lin_ramped",
            "ang_raw_tilt", "ang_norm", "ang_after_deadzone", "ang_after_expo", "ang_target", "ang_ramped",
            "flags"
        ])
        print(f"[TRACE] Logging per-frame trace to {trace_path}")

    current_result = {
        "linear": 0,
        "angular": 0,
        "flags": 0,
        "debug": {
            "state": "IDLE",
            "anchor": None,
            "smoothed_hand": None,
            "smoothed_tilt": 0.0,
            "smoothed_scale": 80.0,
            "finger_extension": 0.0,
            "pre_ramp_linear": 0,
            "pre_ramp_angular": 0,
            "linear_stages": {"raw": 0.0, "norm": 0.0, "after_deadzone": 0.0, "after_expo": 0.0, "target": 0, "ramped": 0},
            "angular_stages": {"raw": 0.0, "norm": 0.0, "after_deadzone": 0.0, "after_expo": 0.0, "target": 0, "ramped": 0},
            "latched_mode": "NORMAL",
            "neutral_tilt": 0.0,
            "neutral_y": 240.0,
        },
    }
    tracking_res = None

    try:
        while True:
            frame_raw, frame_time = cam_thread.read_latest()
            if frame_raw is None:
                time.sleep(0.005)
                continue

            now = time.time()
            now_ms = int(now * 1000)
            camera_latency_ms = (now - frame_time) * 1000.0

            h, w = frame_raw.shape[:2]
            frame_rgb = cv2.cvtColor(frame_raw, cv2.COLOR_BGR2RGB)

            # 1. MediaPipe Gesture Recognition
            try:
                tracking_res = tracker.process(frame_rgb, timestamp_ms=now_ms)
                frame_input = {
                    "landmarks": tracking_res.landmarks,
                    "gesture": tracking_res.gesture,
                    "confidence": tracking_res.gesture_confidence,
                    "width": w,
                    "height": h,
                }
                current_result = pipeline.step(frame_input, now_ms)

                if trace_writer:
                    d = current_result["debug"]
                    ls = d.get("linear_stages", {})
                    as_ = d.get("angular_stages", {})
                    anc = d.get("anchor")
                    sh = d.get("smoothed_hand")
                    trace_writer.writerow([
                        now_ms,
                        tracking_res.gesture or "",
                        f"{tracking_res.gesture_confidence:.3f}",
                        d.get("state", ""),
                        1 if tracking_res.landmarks else 0,
                        f"{sh[0]:.2f}" if sh else "",
                        f"{sh[1]:.2f}" if sh else "",
                        f"{d.get('smoothed_scale') or 0.0:.2f}",
                        f"{d.get('smoothed_tilt') or 0.0:.2f}",
                        f"{d.get('finger_extension') or 0.0:.3f}",
                        f"{anc[0]:.2f}" if anc else "",
                        f"{anc[1]:.2f}" if anc else "",
                        f"{ls.get('raw', 0.0):.4f}",
                        f"{ls.get('norm', 0.0):.4f}",
                        f"{ls.get('after_deadzone', 0.0):.4f}",
                        f"{ls.get('after_expo', 0.0):.4f}",
                        ls.get("target", 0),
                        current_result["linear"],
                        f"{as_.get('raw', 0.0):.4f}",
                        f"{as_.get('norm', 0.0):.4f}",
                        f"{as_.get('after_deadzone', 0.0):.4f}",
                        f"{as_.get('after_expo', 0.0):.4f}",
                        as_.get("target", 0),
                        current_result["angular"],
                        current_result["flags"],
                    ])
            except Exception as e:
                print(f"[WARN] Frame processing error: {e}")

            # 2. Decoupled UDP Transmission (~20 Hz)
            if (now - last_udp_send_time) >= udp_interval:
                is_estop = bool(current_result["flags"] & (1 << 0))
                is_low_conf = bool(current_result["flags"] & (1 << 1))
                sender.send(
                    linear=current_result["linear"],
                    angular=current_result["angular"],
                    estop=is_estop,
                    low_confidence=is_low_conf,
                )
                last_udp_send_time = now

            # 3. FPS calculation
            frame_count += 1
            if (now - fps_start_time) >= 1.0:
                fps = frame_count / (now - fps_start_time)
                frame_count = 0
                fps_start_time = now

            # 4. Preview Window Rendering
            if not args.no_gui:
                # Mirroring is a display option only
                if pipeline.mirror_preview:
                    display_frame = cv2.flip(frame_raw, 1)
                else:
                    display_frame = frame_raw.copy()

                draw_hud(display_frame, current_result, tracking_res, pipeline, fps, camera_latency_ms, show_debug)
                cv2.imshow("Vision-Based AI Gesture Controller", display_frame)

                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
                elif key == ord("m"):
                    pipeline.set_mirror_preview(not pipeline.mirror_preview)
                    print(f"[HOTKEY] Mirror preview: {pipeline.mirror_preview}")
                elif key == ord("j"):
                    new_mode = "joystick" if pipeline.control_mode == "classic" else "classic"
                    pipeline.set_control_mode(new_mode)
                    print(f"[HOTKEY] Control mode: {pipeline.control_mode.upper()}")
                elif key in (ord("+"), ord("=")):
                    pipeline.set_sensitivity(min(3.0, pipeline.sensitivity + 0.1))
                    print(f"[HOTKEY] Sensitivity: {pipeline.sensitivity:.1f}x")
                elif key in (ord("-"), ord("_")):
                    pipeline.set_sensitivity(max(0.1, pipeline.sensitivity - 0.1))
                    print(f"[HOTKEY] Sensitivity: {pipeline.sensitivity:.1f}x")
                elif key == ord("d"):
                    show_debug = not show_debug
                    print(f"[HOTKEY] Debug readout: {show_debug}")

    except KeyboardInterrupt:
        print("\n[CONTROLLER] Interrupted by user.")
    finally:
        print("[CONTROLLER] Shutting down... Sending failsafe STOP packet.")
        try:
            sender.send(linear=0, angular=0, estop=True, low_confidence=False)
        except Exception:
            pass
        cam_thread.stop()
        if not args.no_gui:
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass
        tracker.close()
        sender.close()
        print("[CONTROLLER] Clean shutdown finished.")


if __name__ == "__main__":
    main()
