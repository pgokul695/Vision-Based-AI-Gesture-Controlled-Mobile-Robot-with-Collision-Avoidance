"""Unit tests for individual pipeline components in isolation:
- One Euro filter
- Angle computation with aspect correction
- Hysteresis state machine
- Asymmetric slew limiter
"""

import math
import pytest

from gesture.pipeline import (
    OneEuroFilter,
    SlewLimiter,
    GesturePipeline,
    apply_axis_shaping,
    FLAG_ESTOP,
    FLAG_LOW_CONFIDENCE,
    FLAG_FUN_TRICK,
    FLAG_TURBO,
    FLAG_PRECISION,
)
from vectors.generator import make_hand


def test_one_euro_filter_smoothing():
    f = OneEuroFilter(min_cutoff=1.0, beta=0.01, d_cutoff=1.0)
    # First frame returns exact value
    val0 = f.filter(10.0, 0)
    assert val0 == 10.0

    # Slow change should be heavily filtered
    val1 = f.filter(10.5, 50)
    assert 10.0 < val1 < 10.5

    # Fast jump: filter adapts and increases cutoff
    f.reset()
    f.filter(0.0, 0)
    fast_val = f.filter(100.0, 50)
    assert fast_val > 10.0  # Cutoff opened up for quick response


def test_angle_computation_aspect_invariance():
    """Verify hand tilt angle calculation is identical across 16:9, 4:3, and portrait."""
    pipeline = GesturePipeline()
    tilt_target = 25.0

    for w, h in [(1920.0, 1080.0), (1280.0, 720.0), (640.0, 480.0), (480.0, 640.0), (360.0, 640.0)]:
        frame = make_hand(cx=0.5, cy=0.5, scale=100.0, tilt_deg=tilt_target, width=w, height=h)
        kx, ky, tilt_deg, scale = pipeline._extract_features(frame["landmarks"], w, h)
        assert abs(tilt_deg - tilt_target) < 0.1, f"Failed on resolution {w}x{h}: got {tilt_deg}"


def test_state_machine_hysteresis_and_grace():
    """Verify enter_conf (0.7), exit_conf (0.4), engage_frames (4), and grace_ms (150)."""
    p = GesturePipeline()
    t_ms = 100

    # Frame 1-3 with conf=0.75: ENGAGING
    for i in range(3):
        t_ms += 50
        res = p.step(make_hand(gesture="Open_Palm", confidence=0.75), t_ms)
        assert res["debug"]["state"] == "ENGAGING"
        assert res["linear"] == 0

    # Frame 4: DRIVING
    t_ms += 50
    res = p.step(make_hand(gesture="Open_Palm", confidence=0.75), t_ms)
    assert res["debug"]["state"] == "DRIVING"

    # Drops to conf=0.5 (above exit_conf 0.4): stays in DRIVING
    t_ms += 50
    res = p.step(make_hand(gesture="Open_Palm", confidence=0.5), t_ms)
    assert res["debug"]["state"] == "DRIVING"

    # Drops below exit_conf (conf=0.3): enters GRACE
    t_ms += 50
    res = p.step(make_hand(gesture="Open_Palm", confidence=0.3), t_ms)
    assert res["debug"]["state"] == "GRACE"

    # Recover within grace window: back to DRIVING
    t_ms += 50
    res = p.step(make_hand(gesture="Open_Palm", confidence=0.6), t_ms)
    assert res["debug"]["state"] == "DRIVING"

    # Drop out completely
    t_ms += 50
    res = p.step({"landmarks": None, "gesture": None, "confidence": 0.0, "width": 640.0, "height": 480.0}, t_ms)
    assert res["debug"]["state"] == "GRACE"

    # Grace expires (150ms elapsed) -> IDLE
    t_ms += 200
    res = p.step({"landmarks": None, "gesture": None, "confidence": 0.0, "width": 640.0, "height": 480.0}, t_ms)
    assert res["debug"]["state"] == "IDLE"


def test_estop_instant_within_two_frames_and_bypasses_ramp():
    """Verify Closed_Fist triggers estop on frame 2 and immediately zeroes motion."""
    p = GesturePipeline()
    t_ms = 100

    # Engage
    for _ in range(4):
        t_ms += 50
        p.step(make_hand(cx=0.5, cy=0.1, gesture="Open_Palm", confidence=0.8), t_ms)

    # Fist frame 1
    t_ms += 50
    res1 = p.step(make_hand(gesture="Closed_Fist", confidence=0.9), t_ms)
    # Fist frame 2 -> Must be in ESTOP immediately
    t_ms += 50
    res2 = p.step(make_hand(gesture="Closed_Fist", confidence=0.9), t_ms)

    assert res2["debug"]["state"] == "ESTOP"
    assert res2["linear"] == 0
    assert res2["angular"] == 0
    assert (res2["flags"] & FLAG_ESTOP) != 0


def test_slew_limiter_asymmetric_and_sign_change():
    """Verify accel_rate (250) vs decel_rate (800) and sign change through zero."""
    limiter = SlewLimiter(accel_rate=250.0, decel_rate=800.0, steer_rate=400.0)

    # Start at 0, target 100, dt = 0.1s
    # Accel step = 250 * 0.1 = 25
    lin, ang = limiter.step(100, 0, 100)
    assert lin == 100  # First frame initializes
    limiter.reset()

    # Initialize at 0
    limiter.step(0, 0, 100)
    # Step towards 100 with dt=0.2s -> max accel = 50
    lin, _ = limiter.step(100, 0, 300)
    assert lin == 50

    # Now step towards 0 with dt=0.05s -> decel rate = 800 -> decel step = 40
    # From 50 down by 40 = 10
    lin, _ = limiter.step(0, 0, 350)
    assert lin == 10

    # Direction change: from 10 to -50 with dt=0.05s (50ms)
    # Time to 0: 10 / 800 = 0.0125s
    # Remaining time: 0.0375s
    # Accel in negative: 250 * 0.0375 = 9.375 -> rounded to -9
    lin, _ = limiter.step(-50, 0, 400)
    assert lin == -9


def test_axis_shaping():
    """Test deadzone with rescale, expo, and clamping."""
    # Within deadzone
    assert apply_axis_shaping(0.05, full_scale=1.0, deadzone=0.10, sensitivity=1.0, expo=0.4) == 0

    # Just above deadzone starts small (smooth onset)
    val = apply_axis_shaping(0.12, full_scale=1.0, deadzone=0.10, sensitivity=1.0, expo=0.4)
    assert 0 < val < 5

    # At full scale
    val_fs = apply_axis_shaping(1.0, full_scale=1.0, deadzone=0.10, sensitivity=1.0, expo=0.4)
    assert val_fs == 100

    # Beyond full scale clamped to 100
    val_over = apply_axis_shaping(1.5, full_scale=1.0, deadzone=0.10, sensitivity=1.0, expo=0.4)
    assert val_over == 100

    # Symmetry for negative
    val_neg = apply_axis_shaping(-1.0, full_scale=1.0, deadzone=0.10, sensitivity=1.0, expo=0.4)
    assert val_neg == -100
