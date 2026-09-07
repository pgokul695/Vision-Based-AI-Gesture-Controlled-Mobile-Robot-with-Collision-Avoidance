"""Main application loop for vision-based AI gesture controller.

Captures webcam frames, runs MediaPipe Tasks GestureRecognizer,
computes differential-drive motion commands via pure hybrid mapping,
and streams 10-byte binary UDP datagrams at a fixed ~20 Hz rate to the robot.
"""

import argparse
from pathlib import Path
import sys
import time
from typing import Optional

# Resolve imports for local modules and shared protocol
src_dir = Path(__file__).resolve().parent
repo_root = src_dir.parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from gesture.hand_tracker import HandTracker, HandTrackingResult
from gesture.motion_mapper import compute_motion, MotionCommand, NEUTRAL_Y, THROTTLE_DEADZONE
from network.udp_sender import UdpSender


def parse_args():
    parser = argparse.ArgumentParser(
        description="Vision-Based AI Gesture Controller (Hybrid Mapping)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Target robot IP / hostname")
    parser.add_argument("--port", type=int, default=8888, help="Target robot UDP port")
    parser.add_argument("--camera-index", type=int, default=0, help="Webcam device index")
    parser.add_argument("--rate", type=float, default=20.0, help="UDP transmission rate in Hz")
    parser.add_argument("--model-path", type=str, default=None, help="Path to gesture_recognizer.task model file")
    parser.add_argument("--no-gui", action="store_true", help="Run in headless mode without cv2.imshow GUI")
    return parser.parse_args()


def draw_hud(frame_bgr, cmd: MotionCommand, tracking: Optional[HandTrackingResult], fps: float):
    """Draws on-screen debug HUD displaying gesture status and motion parameters."""
    try:
        import cv2
    except ImportError:
        return

    h, w = frame_bgr.shape[:2]

    # Draw neutral throttle guidelines
    top_deadzone_y = int((NEUTRAL_Y - THROTTLE_DEADZONE) * h)
    bot_deadzone_y = int((NEUTRAL_Y + THROTTLE_DEADZONE) * h)
    center_neutral_y = int(NEUTRAL_Y * h)

    cv2.line(frame_bgr, (0, center_neutral_y), (w, center_neutral_y), (100, 100, 100), 1)
    cv2.line(frame_bgr, (0, top_deadzone_y), (w, top_deadzone_y), (0, 255, 0), 1)
    cv2.line(frame_bgr, (0, bot_deadzone_y), (w, bot_deadzone_y), (0, 0, 255), 1)

    # Status Banner
    if cmd.estop:
        status_text = "STATUS: [EMERGENCY STOP (Closed Fist)]"
        status_color = (0, 0, 255)
    elif cmd.low_confidence:
        status_text = "STATUS: [DISARMED / LOW CONFIDENCE]"
        status_color = (0, 165, 255)
    elif tracking and tracking.gesture == "Open_Palm":
        status_text = "STATUS: [ACTIVE DRIVING (Open Palm)]"
        status_color = (0, 255, 0)
    else:
        status_text = "STATUS: [STANDBY]"
        status_color = (200, 200, 200)

    # Semi-transparent background panel for text
    overlay = frame_bgr.copy()
    cv2.rectangle(overlay, (10, 10), (450, 160), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.7, frame_bgr, 0.3, 0, frame_bgr)

    gesture_label = tracking.gesture if (tracking and tracking.gesture) else "None"
    conf_val = (tracking.gesture_confidence * 100.0) if (tracking and tracking.gesture_confidence) else 0.0

    cv2.putText(frame_bgr, status_text, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.55, status_color, 2)
    cv2.putText(
        frame_bgr,
        f"Gesture: {gesture_label} ({conf_val:.1f}%)",
        (20, 65),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        1,
    )
    cv2.putText(
        frame_bgr,
        f"Linear:  {cmd.linear:+4d}%  |  Angular: {cmd.angular:+4d}%",
        (20, 95),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        1,
    )
    cv2.putText(
        frame_bgr,
        f"E-Stop: {cmd.estop}  |  Low-Conf: {cmd.low_confidence}",
        (20, 125),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (200, 200, 200),
        1,
    )
    cv2.putText(
        frame_bgr,
        f"FPS: {fps:.1f} | Press 'q' to exit",
        (20, 150),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (150, 150, 150),
        1,
    )


def main():
    args = parse_args()
    print(f"[CONTROLLER] Target UDP: {args.host}:{args.port}")
    print(f"[CONTROLLER] Desired transmission rate: {args.rate} Hz")

    try:
        tracker = HandTracker(model_path=args.model_path)
    except FileNotFoundError as err:
        print(f"\n[ERROR] {err}\n", file=sys.stderr)
        sys.exit(1)
    except ImportError as err:
        print(f"\n[ERROR] {err}\n", file=sys.stderr)
        sys.exit(1)

    try:
        import cv2
    except ImportError:
        print("[ERROR] OpenCV (cv2) is required to run the video capture loop.", file=sys.stderr)
        sys.exit(1)

    sender = UdpSender(host=args.host, port=args.port)
    sender.start()

    cap = cv2.VideoCapture(args.camera_index)
    if not cap.isOpened():
        print(f"[ERROR] Could not open camera device at index {args.camera_index}.", file=sys.stderr)
        sender.close()
        tracker.close()
        sys.exit(1)

    udp_interval = 1.0 / args.rate
    last_udp_send_time = 0.0
    fps = 0.0
    frame_count = 0
    fps_start_time = time.time()

    current_cmd = MotionCommand(linear=0, angular=0, estop=False, low_confidence=True)
    tracking_res = None

    print("[CONTROLLER] Controller running. Press 'q' or Ctrl+C to quit.")

    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                print("[WARN] Failed to grab camera frame. Retrying...")
                time.sleep(0.05)
                continue

            # Mirror frame horizontally for intuitive interaction
            frame = cv2.flip(frame, 1)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            now = time.time()
            now_ms = int(now * 1000)

            # 1. Process hand tracking & gesture recognition
            try:
                tracking_res = tracker.process(frame_rgb, timestamp_ms=now_ms)
                current_cmd = compute_motion(
                    landmarks=tracking_res.landmarks,
                    gesture=tracking_res.gesture,
                    gesture_confidence=tracking_res.gesture_confidence,
                )
            except Exception as e:
                print(f"[WARN] Error processing frame: {e}")
                current_cmd = MotionCommand(linear=0, angular=0, estop=False, low_confidence=True)

            # 2. Decoupled UDP Transmission (~20 Hz)
            if (now - last_udp_send_time) >= udp_interval:
                sender.send(
                    linear=current_cmd.linear,
                    angular=current_cmd.angular,
                    estop=current_cmd.estop,
                    low_confidence=current_cmd.low_confidence,
                )
                last_udp_send_time = now

            # 3. Calculate display FPS
            frame_count += 1
            if (now - fps_start_time) >= 1.0:
                fps = frame_count / (now - fps_start_time)
                frame_count = 0
                fps_start_time = now

            # 4. Render HUD and display window
            if not args.no_gui:
                draw_hud(frame, current_cmd, tracking_res, fps)
                cv2.imshow("Gesture Controller (Hybrid)", frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):  # 'q' or ESC
                    break

    except KeyboardInterrupt:
        print("\n[CONTROLLER] Interrupted by user.")
    finally:
        print("[CONTROLLER] Shutting down... Sending failsafe STOP packet.")
        try:
            sender.send(linear=0, angular=0, estop=True, low_confidence=False)
        except Exception:
            pass
        cap.release()
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
