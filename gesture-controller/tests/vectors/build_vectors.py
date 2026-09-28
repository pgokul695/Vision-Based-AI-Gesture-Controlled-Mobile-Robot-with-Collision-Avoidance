#!/usr/bin/env python3
"""Build golden test vectors using synthetic hand generator and Python GesturePipeline."""

import json
from pathlib import Path
import sys

src_dir = Path(__file__).resolve().parent.parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from gesture.pipeline import GesturePipeline
from generator import make_hand


def build_scenario_neutral():
    """Scenario 1: Neutral hand engagement and steady holding."""
    pipeline = GesturePipeline()
    frames = []
    t_ms = 0
    # 4 frames engage + 6 frames steady driving
    for i in range(10):
        t_ms += 50
        frame = make_hand(cx=0.5, cy=0.5, scale=80.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9)
        frames.append((frame, t_ms))
    return "static_neutral", pipeline, frames


def build_scenario_steady_tilt_aspects():
    """Scenario 2: Steady tilt (+30 deg) across 16:9, 4:3, and portrait aspect ratios."""
    scenarios = []
    aspects = [
        ("tilt_30_16_9", 1280.0, 720.0),
        ("tilt_30_4_3", 640.0, 480.0),
        ("tilt_30_portrait", 480.0, 640.0),
    ]
    for name, w, h in aspects:
        pipeline = GesturePipeline()
        # Engage with fixed neutral tilt
        pipeline.map_cfg["tilt_neutral"] = "fixed"
        frames = []
        t_ms = 0
        # 4 frames engage at 0 tilt
        for _ in range(4):
            t_ms += 50
            frames.append((make_hand(cx=0.5, cy=0.5, scale=80.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9, width=w, height=h), t_ms))
        # 10 frames at +30 deg tilt
        for _ in range(10):
            t_ms += 50
            frames.append((make_hand(cx=0.5, cy=0.5, scale=80.0, tilt_deg=30.0, gesture="Open_Palm", confidence=0.9, width=w, height=h), t_ms))
        scenarios.append((name, pipeline, frames))
    return scenarios


def build_scenario_joystick():
    """Scenario 3: Joystick mode deflection in 4 directions."""
    pipeline = GesturePipeline()
    pipeline.set_control_mode("joystick")
    frames = []
    t_ms = 0
    # Engage at center
    for _ in range(4):
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=0.5, scale=80.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9), t_ms))
    # Move forward (upwards: cy decreases to 0.35)
    for _ in range(6):
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=0.35, scale=80.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9), t_ms))
    # Move back to center
    for _ in range(4):
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=0.5, scale=80.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9), t_ms))
    # Move right (cx increases to 0.65)
    for _ in range(6):
        t_ms += 50
        frames.append((make_hand(cx=0.65, cy=0.5, scale=80.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9), t_ms))
    return "joystick_deflections", pipeline, frames


def build_scenario_flicker():
    """Scenario 4: Palm dropout for 2 frames during driving (grace period test)."""
    pipeline = GesturePipeline()
    frames = []
    t_ms = 0
    # Engage
    for _ in range(4):
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=0.3, scale=80.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9), t_ms))
    # Drive for 3 frames
    for _ in range(3):
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=0.3, scale=80.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9), t_ms))
    # Dropout 2 frames (None / low confidence, 100ms total <= 150ms grace)
    for _ in range(2):
        t_ms += 50
        frames.append(({"landmarks": None, "gesture": None, "confidence": 0.0, "width": 640.0, "height": 480.0}, t_ms))
    # Hand returns
    for _ in range(4):
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=0.3, scale=80.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9), t_ms))
    return "flicker_grace", pipeline, frames


def build_scenario_estop():
    """Scenario 5: Closed_Fist emergency stop triggers instantly within 2 frames and bypasses ramp."""
    pipeline = GesturePipeline()
    frames = []
    t_ms = 0
    # Engage and drive fast forward
    for _ in range(4):
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=0.2, scale=80.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9), t_ms))
    for _ in range(5):
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=0.2, scale=80.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9), t_ms))
    # Fist frame 1
    t_ms += 50
    frames.append((make_hand(cx=0.5, cy=0.2, scale=80.0, tilt_deg=0.0, gesture="Closed_Fist", confidence=0.9), t_ms))
    # Fist frame 2 -> MUST BE ESTOP
    t_ms += 50
    frames.append((make_hand(cx=0.5, cy=0.2, scale=80.0, tilt_deg=0.0, gesture="Closed_Fist", confidence=0.9), t_ms))
    # Fist released
    t_ms += 50
    frames.append((make_hand(cx=0.5, cy=0.2, scale=80.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9), t_ms))
    return "estop_instant", pipeline, frames


def build_scenario_fun_trick():
    """Scenario 6: ILoveYou trick hold (500ms), single trigger, and cooldown enforcement."""
    pipeline = GesturePipeline()
    frames = []
    t_ms = 0
    # Show ILoveYou for 15 frames (750ms at 50ms/frame)
    for _ in range(15):
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=0.5, scale=80.0, tilt_deg=0.0, gesture="ILoveYou", confidence=0.9), t_ms))
    return "fun_trick_cooldown", pipeline, frames


def build_scenario_mode_latches():
    """Scenario 7: Thumb_Up toggles turbo, Victory toggles precision, auto-clear on timeout."""
    pipeline = GesturePipeline()
    frames = []
    t_ms = 0
    # Hold Thumb_Up for 9 frames (450ms > 400ms mode_hold_ms)
    for _ in range(9):
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=0.5, scale=80.0, tilt_deg=0.0, gesture="Thumb_Up", confidence=0.9), t_ms))
    # Engage Open_Palm driving with turbo latched
    for _ in range(6):
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=0.4, scale=80.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9), t_ms))
    # Drop hand for 2.2s (> 2000ms mode_timeout_ms) -> auto-clears latch
    for _ in range(5):
        t_ms += 500
        frames.append(({"landmarks": None, "gesture": None, "confidence": 0.0, "width": 640.0, "height": 480.0}, t_ms))
    return "mode_latches_timeout", pipeline, frames


def build_scenario_ramp_step():
    """Scenario 8: Slew limiter response to step input and full sign change."""
    pipeline = GesturePipeline()
    pipeline.map_cfg["throttle_neutral"] = "frame_center"
    frames = []
    t_ms = 0
    # Engage at center
    for _ in range(4):
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=0.5, scale=80.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9), t_ms))
    # Step to full forward (cy=0.1) for 10 frames
    for _ in range(10):
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=0.1, scale=80.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9), t_ms))
    # Step to full reverse (cy=0.9) for 12 frames
    for _ in range(12):
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=0.9, scale=80.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9), t_ms))
    return "ramp_step_response", pipeline, frames


def generate_all_golden_vectors():
    scenarios_list = [
        build_scenario_neutral(),
        build_scenario_joystick(),
        build_scenario_flicker(),
        build_scenario_estop(),
        build_scenario_fun_trick(),
        build_scenario_mode_latches(),
        build_scenario_ramp_step(),
    ]
    # Add steady tilt scenarios
    for s in build_scenario_steady_tilt_aspects():
        scenarios_list.append(s)

    all_data = {}
    for name, pipeline, frames in scenarios_list:
        scenario_records = []
        for frame, t_ms in frames:
            result = pipeline.step(frame, t_ms)
            scenario_records.append({
                "t_ms": t_ms,
                "input_frame": frame,
                "expected": {
                    "linear": result["linear"],
                    "angular": result["angular"],
                    "flags": result["flags"],
                    "state": result["debug"]["state"],
                    "latched_mode": result["debug"]["latched_mode"],
                }
            })
        all_data[name] = {
            "config": pipeline.config,
            "steps": scenario_records
        }

    out_path = Path(__file__).resolve().parent / "golden_vectors.json"
    out_path.write_text(json.dumps(all_data, indent=2), encoding="utf-8")
    print(f"Generated {len(all_data)} golden vector scenarios -> {out_path}")


if __name__ == "__main__":
    generate_all_golden_vectors()
