"""Gesture tracking and motion mapping package."""

from .hand_tracker import HandTracker, HandTrackingResult
from .motion_mapper import (
    compute_motion,
    MotionCommand,
    MAX_TILT_DEG,
    THROTTLE_DEADZONE,
    THROTTLE_FULL_RANGE,
    NEUTRAL_Y,
    DEFAULT_MIN_CONFIDENCE,
)

__all__ = [
    "HandTracker",
    "HandTrackingResult",
    "compute_motion",
    "MotionCommand",
    "MAX_TILT_DEG",
    "THROTTLE_DEADZONE",
    "THROTTLE_FULL_RANGE",
    "NEUTRAL_Y",
    "DEFAULT_MIN_CONFIDENCE",
]
