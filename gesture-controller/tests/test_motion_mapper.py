"""Unit tests for pure function motion mapping logic.

Tests compute_motion directly using synthetic hand landmark fixtures without any
camera, MediaPipe runtime, or network dependencies.
"""

from typing import List, Tuple
import pytest
import sys
from pathlib import Path

# Add source path
test_dir = Path(__file__).resolve().parent
src_dir = test_dir.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from gesture.motion_mapper import (
    compute_motion,
    MotionCommand,
    NEUTRAL_Y,
    THROTTLE_DEADZONE,
    THROTTLE_FULL_RANGE,
    MAX_TILT_DEG,
    LANDMARK_WRIST,
    LANDMARK_INDEX_MCP,
    LANDMARK_PINKY_MCP,
)


def create_mock_landmarks(
    wrist_y: float = NEUTRAL_Y,
    index_mcp: Tuple[float, float] = (0.4, 0.4),
    pinky_mcp: Tuple[float, float] = (0.6, 0.4),
) -> List[Tuple[float, float, float]]:
    """Generates a synthetic 21-landmark array for testing."""
    landmarks = [(0.5, 0.5, 0.0)] * 21
    landmarks[LANDMARK_WRIST] = (0.5, wrist_y, 0.0)
    landmarks[LANDMARK_INDEX_MCP] = (index_mcp[0], index_mcp[1], 0.0)
    landmarks[LANDMARK_PINKY_MCP] = (pinky_mcp[0], pinky_mcp[1], 0.0)
    return landmarks


def test_no_hand_detected():
    """No landmarks or no gesture yields zero motion with low_confidence=True."""
    # None landmarks
    res1 = compute_motion(None, "Open_Palm", 0.9)
    assert res1.linear == 0
    assert res1.angular == 0
    assert not res1.estop
    assert res1.low_confidence

    # None gesture
    landmarks = create_mock_landmarks()
    res2 = compute_motion(landmarks, None, 0.9)
    assert res2.linear == 0
    assert res2.angular == 0
    assert not res2.estop
    assert res2.low_confidence

    # Incomplete landmark list (< 21 points)
    res3 = compute_motion([(0.0, 0.0, 0.0)] * 10, "Open_Palm", 0.9)
    assert res3.linear == 0
    assert res3.angular == 0
    assert res3.low_confidence


def test_closed_fist_forces_estop():
    """Closed_Fist must force estop=True even if hand is in full-throttle position."""
    # Hand positioned high (full throttle forward) but closed fist
    landmarks = create_mock_landmarks(wrist_y=0.1)
    res = compute_motion(landmarks, "Closed_Fist", 0.95)

    assert res.linear == 0
    assert res.angular == 0
    assert res.estop is True
    assert res.low_confidence is False


def test_non_drive_gestures_yield_zero_motion():
    """Any gesture other than Open_Palm or Closed_Fist disarms driving without e-stop."""
    landmarks = create_mock_landmarks(wrist_y=0.1)  # Raised hand

    for gesture in ["Thumb_Up", "Thumb_Down", "Pointing_Up", "Victory", "ILoveYou"]:
        res = compute_motion(landmarks, gesture, 0.9)
        assert res.linear == 0
        assert res.angular == 0
        assert not res.estop


def test_low_confidence_open_palm_disarmed():
    """Open_Palm with confidence below threshold must not arm driving."""
    landmarks = create_mock_landmarks(wrist_y=0.1)
    res = compute_motion(landmarks, "Open_Palm", gesture_confidence=0.55, min_confidence=0.6)

    assert res.linear == 0
    assert res.angular == 0
    assert not res.estop
    assert res.low_confidence is True


def test_neutral_wrist_deadzone():
    """Wrist within deadzone band produces linear == 0."""
    # Exactly on neutral line
    lm_exact = create_mock_landmarks(wrist_y=NEUTRAL_Y)
    res_exact = compute_motion(lm_exact, "Open_Palm", 0.9)
    assert res_exact.linear == 0

    # Within upper deadzone (e.g. 0.5 - 0.04)
    lm_upper = create_mock_landmarks(wrist_y=NEUTRAL_Y - (THROTTLE_DEADZONE * 0.8))
    res_upper = compute_motion(lm_upper, "Open_Palm", 0.9)
    assert res_upper.linear == 0

    # Within lower deadzone (e.g. 0.5 + 0.04)
    lm_lower = create_mock_landmarks(wrist_y=NEUTRAL_Y + (THROTTLE_DEADZONE * 0.8))
    res_lower = compute_motion(lm_lower, "Open_Palm", 0.9)
    assert res_lower.linear == 0


def test_throttle_forward_raised_hand():
    """Raised hand (lower y) produces positive forward linear motion."""
    # Raised to full range: wrist_y = NEUTRAL_Y - THROTTLE_FULL_RANGE = 0.5 - 0.35 = 0.15
    lm_full = create_mock_landmarks(wrist_y=NEUTRAL_Y - THROTTLE_FULL_RANGE)
    res_full = compute_motion(lm_full, "Open_Palm", 0.9)
    assert res_full.linear == 100
    assert res_full.angular == 0

    # Raised beyond full range (e.g. 0.05) clamps to 100
    lm_over = create_mock_landmarks(wrist_y=0.05)
    res_over = compute_motion(lm_over, "Open_Palm", 0.9)
    assert res_over.linear == 100

    # Raised midway: wrist_y = 0.5 - 0.20 = 0.30
    lm_mid = create_mock_landmarks(wrist_y=0.30)
    res_mid = compute_motion(lm_mid, "Open_Palm", 0.9)
    assert 40 <= res_mid.linear <= 60


def test_throttle_reverse_lowered_hand():
    """Lowered hand (higher y) produces negative reverse linear motion."""
    # Lowered to full range: wrist_y = NEUTRAL_Y + THROTTLE_FULL_RANGE = 0.5 + 0.35 = 0.85
    lm_full = create_mock_landmarks(wrist_y=NEUTRAL_Y + THROTTLE_FULL_RANGE)
    res_full = compute_motion(lm_full, "Open_Palm", 0.9)
    assert res_full.linear == -100
    assert res_full.angular == 0

    # Lowered beyond full range clamps to -100
    lm_over = create_mock_landmarks(wrist_y=0.95)
    res_over = compute_motion(lm_over, "Open_Palm", 0.9)
    assert res_over.linear == -100


def test_steering_knuckle_tilt():
    """Knuckle angle between Index-MCP and Pinky-MCP maps to angular steering."""
    # Level hand (dy == 0) -> angular == 0
    lm_level = create_mock_landmarks(
        index_mcp=(0.4, 0.4),
        pinky_mcp=(0.6, 0.4),
    )
    res_level = compute_motion(lm_level, "Open_Palm", 0.9)
    assert res_level.angular == 0

    # Tilted right (clockwise): pinky is lower (higher y) than index
    # dx = 0.2, dy = 0.1 -> atan2(0.1, 0.2) = 26.56 degrees
    # Expected angular: round((26.56 / 40.0) * 100) = 66
    lm_right = create_mock_landmarks(
        index_mcp=(0.4, 0.4),
        pinky_mcp=(0.6, 0.5),
    )
    res_right = compute_motion(lm_right, "Open_Palm", 0.9)
    assert res_right.angular > 0
    assert 60 <= res_right.angular <= 70

    # Tilted left (counter-clockwise): pinky is higher (lower y) than index
    # dx = 0.2, dy = -0.1 -> atan2(-0.1, 0.2) = -26.56 degrees
    lm_left = create_mock_landmarks(
        index_mcp=(0.4, 0.4),
        pinky_mcp=(0.6, 0.3),
    )
    res_left = compute_motion(lm_left, "Open_Palm", 0.9)
    assert res_left.angular < 0
    assert -70 <= res_left.angular <= -60


def test_steering_clamped_at_max_tilt():
    """Tilting beyond +-MAX_TILT_DEG clamps to +-100%."""
    # 45-degree right tilt: dx = 0.2, dy = 0.2 -> 45 deg > 40 deg
    lm_hard_right = create_mock_landmarks(
        index_mcp=(0.4, 0.4),
        pinky_mcp=(0.6, 0.6),
    )
    res_hard_right = compute_motion(lm_hard_right, "Open_Palm", 0.9)
    assert res_hard_right.angular == 100

    # 45-degree left tilt: dx = 0.2, dy = -0.2 -> -45 deg < -40 deg
    lm_hard_left = create_mock_landmarks(
        index_mcp=(0.4, 0.4),
        pinky_mcp=(0.6, 0.2),
    )
    res_hard_left = compute_motion(lm_hard_left, "Open_Palm", 0.9)
    assert res_hard_left.angular == -100
