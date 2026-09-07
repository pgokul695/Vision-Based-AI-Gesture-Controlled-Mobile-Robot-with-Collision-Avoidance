"""Pure-function motion mapping from hand landmarks and gesture classification to robot commands.

This module contains NO hardware, camera, or network dependencies and is designed
to be completely unit-testable in isolation.
"""

from dataclasses import dataclass
import math
from typing import Optional, Sequence, Tuple

# Named tuning constants
MAX_TILT_DEG: float = 40.0         # Hand roll/tilt angle corresponding to 100% steering
THROTTLE_DEADZONE: float = 0.06     # Neutral vertical deadzone (~6% of frame height)
THROTTLE_FULL_RANGE: float = 0.35   # Range from neutral to full throttle (~35% of frame height)
NEUTRAL_Y: float = 0.5              # Center of the neutral throttle band (normalized y)
DEFAULT_MIN_CONFIDENCE: float = 0.6 # Minimum gesture recognition confidence required to drive

# Landmark indices defined by MediaPipe Hand model
LANDMARK_WRIST: int = 0
LANDMARK_INDEX_MCP: int = 5
LANDMARK_PINKY_MCP: int = 17


@dataclass
class MotionCommand:
    """Robot motion command produced by gesture mapping."""

    linear: int = 0             # -100 to 100 %
    angular: int = 0            # -100 to 100 %
    estop: bool = False         # Emergency stop flag
    low_confidence: bool = False # Degraded confidence or un-armed deadman switch


def compute_motion(
    landmarks: Optional[Sequence[Tuple[float, float, float]]],
    gesture: Optional[str],
    gesture_confidence: float,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
) -> MotionCommand:
    """Computes differential drive motion command from hand landmarks and gesture.

    Control Scheme (Hybrid):
    1. No landmarks or no gesture -> zero motion, low_confidence=True.
    2. Closed_Fist -> zero motion, estop=True (hard override).
    3. Low confidence (< min_confidence) -> zero motion, low_confidence=True.
    4. Non-drive gesture (!= Open_Palm) -> zero motion (deadman switch not engaged).
    5. Open_Palm with confidence >= min_confidence -> Continuous mapping:
       - Angular: Knuckle line angle (Index-MCP to Pinky-MCP), clamped to +-MAX_TILT_DEG,
         mapped to -100..100.
       - Linear: Wrist vertical position relative to NEUTRAL_Y, deadzone-filtered by
         THROTTLE_DEADZONE, scaled by THROTTLE_FULL_RANGE, mapped to -100..100.
    """
    # Rule 1: No hand detected or missing gesture
    if landmarks is None or len(landmarks) < 21 or gesture is None:
        return MotionCommand(linear=0, angular=0, estop=False, low_confidence=True)

    # Rule 2: Explicit emergency stop
    if gesture == "Closed_Fist":
        return MotionCommand(linear=0, angular=0, estop=True, low_confidence=False)

    # Rule 3: Low confidence detection
    if gesture_confidence < min_confidence:
        return MotionCommand(linear=0, angular=0, estop=False, low_confidence=True)

    # Rule 4: Deadman switch - only Open_Palm arms active continuous drive
    if gesture != "Open_Palm":
        return MotionCommand(linear=0, angular=0, estop=False, low_confidence=False)

    # Rule 5: Continuous drive mapping (Open_Palm active)
    wrist = landmarks[LANDMARK_WRIST]
    index_mcp = landmarks[LANDMARK_INDEX_MCP]
    pinky_mcp = landmarks[LANDMARK_PINKY_MCP]

    # --- A. Angular Velocity (Steering via Knuckle Tilt) ---
    dx = pinky_mcp[0] - index_mcp[0]
    dy = pinky_mcp[1] - index_mcp[1]

    # Calculate angle of knuckle line
    raw_angle_rad = math.atan2(dy, dx)
    angle_deg = math.degrees(raw_angle_rad)

    # Normalize angle to range [-90, +90] relative to horizontal line
    if angle_deg > 90.0:
        angle_deg -= 180.0
    elif angle_deg < -90.0:
        angle_deg += 180.0

    # Clamp to [-MAX_TILT_DEG, MAX_TILT_DEG]
    clamped_angle = max(-MAX_TILT_DEG, min(MAX_TILT_DEG, angle_deg))
    angular_val = round((clamped_angle / MAX_TILT_DEG) * 100.0)
    angular = int(max(-100, min(100, angular_val)))

    # --- B. Linear Velocity (Throttle via Wrist Height) ---
    wrist_y = wrist[1]
    effective_range = THROTTLE_FULL_RANGE - THROTTLE_DEADZONE
    linear = 0

    if effective_range > 0:
        if wrist_y < (NEUTRAL_Y - THROTTLE_DEADZONE):
            # Hand raised -> forward motion (y decreases upwards)
            displacement = (NEUTRAL_Y - THROTTLE_DEADZONE) - wrist_y
            throttle = min(1.0, displacement / effective_range)
            linear = int(round(throttle * 100.0))
        elif wrist_y > (NEUTRAL_Y + THROTTLE_DEADZONE):
            # Hand lowered -> reverse motion (y increases downwards)
            displacement = wrist_y - (NEUTRAL_Y + THROTTLE_DEADZONE)
            throttle = min(1.0, displacement / effective_range)
            linear = -int(round(throttle * 100.0))

    linear = int(max(-100, min(100, linear)))

    return MotionCommand(
        linear=linear,
        angular=angular,
        estop=False,
        low_confidence=False,
    )
