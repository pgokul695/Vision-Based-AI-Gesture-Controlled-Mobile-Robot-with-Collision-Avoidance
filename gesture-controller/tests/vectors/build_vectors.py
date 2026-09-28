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
        pipeline.map_cfg["tilt_neutral"] = "fixed"
        frames = []
        t_ms = 0
        for _ in range(4):
            t_ms += 50
            frames.append((make_hand(cx=0.5, cy=0.5, scale=80.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9, width=w, height=h), t_ms))
        for _ in range(10):
            t_ms += 50
            frames.append((make_hand(cx=0.5, cy=0.5, scale=80.0, tilt_deg=30.0, gesture="Open_Palm", confidence=0.9, width=w, height=h), t_ms))
        scenarios.append((name, pipeline, frames))
    return scenarios


def build_scenario_tilt_sustained_without_label():
    """Scenario: Tilting hand to +35 deg and -35 deg causes classifier to drop to 'None' (0.2 conf),
    but geometric finger extension sustains DRIVING and produces steering near full lock in both directions.
    """
    pipeline = GesturePipeline()
    pipeline.map_cfg["tilt_neutral"] = "fixed"
    frames = []
    t_ms = 0
    # Engage normally with Open_Palm
    for _ in range(4):
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=0.5, scale=80.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9), t_ms))
    # Tilt to +35 deg while classifier drops label to None / low confidence
    for _ in range(8):
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=0.5, scale=80.0, tilt_deg=35.0, gesture=None, confidence=0.2, curled=False), t_ms))
    # Return to level (0 deg)
    for _ in range(4):
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=0.5, scale=80.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9), t_ms))
    # Tilt to -35 deg while classifier drops label to None / low confidence
    for _ in range(8):
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=0.5, scale=80.0, tilt_deg=-35.0, gesture=None, confidence=0.2, curled=False), t_ms))
    # Return to level (0 deg)
    for _ in range(4):
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=0.5, scale=80.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9), t_ms))
    return "tilt_35_sustained_geometric", pipeline, frames


def build_scenario_classifier_dropout_during_tilt():
    """Scenario: A 1-3 frame classifier dropout during steady tilt (+30 deg) does not leave DRIVING."""
    pipeline = GesturePipeline()
    pipeline.map_cfg["tilt_neutral"] = "fixed"
    frames = []
    t_ms = 0
    # Engage
    for _ in range(4):
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=0.5, scale=80.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9), t_ms))
    # Steady tilt +30 deg with Open_Palm
    for _ in range(4):
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=0.5, scale=80.0, tilt_deg=30.0, gesture="Open_Palm", confidence=0.9), t_ms))
    # 3 frames of classifier dropout (gesture=None, confidence=0.1) while tilted
    for _ in range(3):
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=0.5, scale=80.0, tilt_deg=30.0, gesture=None, confidence=0.1, curled=False), t_ms))
    # Classifier recovers
    for _ in range(5):
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=0.5, scale=80.0, tilt_deg=30.0, gesture="Open_Palm", confidence=0.9), t_ms))
    return "classifier_dropout_during_tilt", pipeline, frames


def build_scenario_symmetric_monotonic_throttle():
    """Scenario: Raising and lowering from anchor giving symmetric, monotonic throttle that reaches +-100 at full scale."""
    pipeline = GesturePipeline()
    pipeline.map_cfg["reverse_scale"] = 1.0  # Fully symmetric
    frames = []
    t_ms = 0
    # Engage at cy=0.50, scale=80.0 (full scale 1.2 * 80 = 96px -> in 480h is 96/480 = 0.20 cy)
    for _ in range(4):
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=0.50, scale=80.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9), t_ms))
    # Raise palm progressively: 0.50 -> 0.45 -> 0.40 -> 0.35 -> 0.30 (full scale -> +100)
    for cy_step in [0.45, 0.40, 0.35, 0.30, 0.30, 0.30]:
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=cy_step, scale=80.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9), t_ms))
    # Return to anchor
    for cy_step in [0.35, 0.40, 0.45, 0.50, 0.50]:
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=cy_step, scale=80.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9), t_ms))
    # Lower palm progressively: 0.50 -> 0.55 -> 0.60 -> 0.65 -> 0.70 (full scale -> -100)
    for cy_step in [0.55, 0.60, 0.65, 0.70, 0.70, 0.70]:
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=cy_step, scale=80.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9), t_ms))
    # Return to anchor
    for cy_step in [0.65, 0.60, 0.55, 0.50, 0.50]:
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=cy_step, scale=80.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9), t_ms))
    return "symmetric_monotonic_throttle", pipeline, frames


def build_scenario_monotonic_anchor_throttle():
    """Scenario: Raise palm above anchor for forward (+100 at full scale), lower below anchor for reduced reverse (-60 at full scale)."""
    pipeline = GesturePipeline()
    frames = []
    t_ms = 0
    # Engage with hand resting at cy=0.60 (natural resting position, anchor set here)
    for _ in range(4):
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=0.60, scale=80.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9), t_ms))
    # Raise palm upward by full scale (96px -> cy = 0.60 - 96/480 = 0.40)
    for cy_step in [0.55, 0.50, 0.45, 0.40, 0.40, 0.40]:
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=cy_step, scale=80.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9), t_ms))
    # Return to resting anchor
    for cy_step in [0.45, 0.50, 0.55, 0.60, 0.60]:
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=cy_step, scale=80.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9), t_ms))
    # Lower palm below anchor by full scale (96px -> cy = 0.60 + 96/480 = 0.80) -> reverse limited to -60
    for cy_step in [0.65, 0.70, 0.75, 0.80, 0.80, 0.80]:
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=cy_step, scale=80.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9), t_ms))
    # Return to resting anchor
    for cy_step in [0.75, 0.70, 0.65, 0.60, 0.60]:
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=cy_step, scale=80.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9), t_ms))
    return "monotonic_anchor_throttle", pipeline, frames


def build_scenario_anchoring_position_invariance():
    """Scenario: Anchoring at different positions (cy=0.7 vs cy=0.3) and hand sizes (scale=80 vs scale=120)
    giving identical deflection outputs.
    """
    pipeline = GesturePipeline()
    frames = []
    t_ms = 0
    # Phase 1: Hand at cy=0.70 (lower frame), scale=80.0
    for _ in range(4):
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=0.70, scale=80.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9), t_ms))
    # Displace upward by 1.0 hand scale (80px in 480h -> 80/480)
    for _ in range(6):
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=0.70 - (80.0 / 480.0), scale=80.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9), t_ms))
    # Remove hand to return to IDLE
    for _ in range(6):
        t_ms += 50
        frames.append(({"landmarks": None, "gesture": None, "confidence": 0.0, "width": 640.0, "height": 480.0}, t_ms))
    # Phase 2: Hand at cy=0.30 (upper frame), scale=120.0
    for _ in range(4):
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=0.30, scale=120.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9), t_ms))
    # Displace upward by 1.0 hand scale (120px in 480h -> 120/480)
    for _ in range(6):
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=0.30 - (120.0 / 480.0), scale=120.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9), t_ms))
    return "anchoring_invariance", pipeline, frames


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
    for _ in range(4):
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=0.3, scale=80.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9), t_ms))
    for _ in range(3):
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=0.3, scale=80.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9), t_ms))
    for _ in range(2):
        t_ms += 50
        frames.append(({"landmarks": None, "gesture": None, "confidence": 0.0, "width": 640.0, "height": 480.0}, t_ms))
    for _ in range(4):
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=0.3, scale=80.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9), t_ms))
    return "flicker_grace", pipeline, frames


def build_scenario_estop():
    """Scenario 5: Closed_Fist emergency stop triggers instantly within 2 frames and bypasses ramp."""
    pipeline = GesturePipeline()
    frames = []
    t_ms = 0
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


def build_scenario_geometric_fist_estop():
    """Scenario: Hand curls into fist without classifier label ('None') -> geometric estop fires within 2 frames."""
    pipeline = GesturePipeline()
    frames = []
    t_ms = 0
    for _ in range(4):
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=0.2, scale=80.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9), t_ms))
    # Curled fist frame 1 with gesture=None
    t_ms += 50
    frames.append((make_hand(cx=0.5, cy=0.2, scale=80.0, tilt_deg=0.0, gesture=None, confidence=0.1, curled=True), t_ms))
    # Curled fist frame 2 -> MUST BE ESTOP
    t_ms += 50
    frames.append((make_hand(cx=0.5, cy=0.2, scale=80.0, tilt_deg=0.0, gesture=None, confidence=0.1, curled=True), t_ms))
    return "geometric_fist_estop", pipeline, frames


def build_scenario_fun_trick():
    """Scenario 6: ILoveYou trick hold (500ms), single trigger, and cooldown enforcement."""
    pipeline = GesturePipeline()
    frames = []
    t_ms = 0
    for _ in range(15):
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=0.5, scale=80.0, tilt_deg=0.0, gesture="ILoveYou", confidence=0.9), t_ms))
    return "fun_trick_cooldown", pipeline, frames


def build_scenario_mode_latches():
    """Scenario 7: Thumb_Up toggles turbo, Victory toggles precision, auto-clear on timeout."""
    pipeline = GesturePipeline()
    frames = []
    t_ms = 0
    for _ in range(9):
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=0.5, scale=80.0, tilt_deg=0.0, gesture="Thumb_Up", confidence=0.9), t_ms))
    for _ in range(6):
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=0.4, scale=80.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9), t_ms))
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
    for _ in range(4):
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=0.5, scale=80.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9), t_ms))
    for _ in range(10):
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=0.1, scale=80.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9), t_ms))
    for _ in range(12):
        t_ms += 50
        frames.append((make_hand(cx=0.5, cy=0.9, scale=80.0, tilt_deg=0.0, gesture="Open_Palm", confidence=0.9), t_ms))
    return "ramp_step_response", pipeline, frames


def generate_all_golden_vectors():
    scenarios_list = [
        build_scenario_neutral(),
        build_scenario_tilt_sustained_without_label(),
        build_scenario_classifier_dropout_during_tilt(),
        build_scenario_symmetric_monotonic_throttle(),
        build_scenario_monotonic_anchor_throttle(),
        build_scenario_anchoring_position_invariance(),
        build_scenario_joystick(),
        build_scenario_flicker(),
        build_scenario_estop(),
        build_scenario_geometric_fist_estop(),
        build_scenario_fun_trick(),
        build_scenario_mode_latches(),
        build_scenario_ramp_step(),
    ]
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
