"""Deterministic synthetic hand landmark generator for testing gesture pipelines."""

import math
from typing import Any, Dict, List, Optional, Tuple

LANDMARK_WRIST = 0
LANDMARK_INDEX_MCP = 5
LANDMARK_MIDDLE_MCP = 9
LANDMARK_RING_MCP = 13
LANDMARK_PINKY_MCP = 17


def make_hand(
    cx: float = 0.5,
    cy: float = 0.5,
    scale: float = 80.0,
    tilt_deg: float = 0.0,
    gesture: str = "Open_Palm",
    confidence: float = 0.9,
    width: float = 640.0,
    height: float = 480.0,
) -> Dict[str, Any]:
    """Generates a synthetic frame with 21 MediaPipe landmarks.

    Args:
        cx: Normalized user-space center X of palm (0.0=left, 1.0=right).
        cy: Normalized center Y of palm (0.0=top, 1.0=bottom).
        scale: Hand scale in pixels (wrist to middle knuckle).
        tilt_deg: Tilt angle in degrees (-90 to +90, positive = tilted to user's right).
        gesture: MediaPipe classified gesture name (e.g. Open_Palm, Closed_Fist).
        confidence: Gesture classification confidence [0.0, 1.0].
        width: Frame width in pixels.
        height: Frame height in pixels.

    Returns:
        Frame dictionary compatible with GesturePipeline.step(frame, t_ms).
    """
    if gesture is None:
        return {
            "landmarks": None,
            "gesture": None,
            "confidence": 0.0,
            "width": width,
            "height": height,
        }

    # Center in user-space pixel coordinates
    kx = cx * width
    ky = cy * height

    theta = math.radians(tilt_deg)
    sin_t = math.sin(theta)
    cos_t = math.cos(theta)

    # Wrist position:
    # vector K - W = (scale * sin(theta), -scale * cos(theta))
    # so W = K - vector
    wx = kx - scale * sin_t
    wy = ky + scale * cos_t

    # Perpendicular unit vector (for knuckle span)
    ux = cos_t
    uy = sin_t

    # Knuckle positions
    p_index = (kx - 0.2 * scale * ux, ky - 0.2 * scale * uy)
    p_middle = (kx, ky)
    p_ring = (kx, ky)
    p_pinky = (kx + 0.2 * scale * ux, ky + 0.2 * scale * uy)

    # Convert all 21 points to normalized raw coordinates
    # Pipeline inverts raw x: user_x = (1.0 - raw_x) * width
    # so raw_x = 1.0 - (user_x / width)
    # raw_y = user_y / height
    def to_raw(px: float, py: float) -> Tuple[float, float, float]:
        raw_x = 1.0 - (px / width)
        raw_y = py / height
        return (round(raw_x, 6), round(raw_y, 6), 0.0)

    landmarks: List[Tuple[float, float, float]] = [to_raw(wx, wy)] * 21
    landmarks[LANDMARK_WRIST] = to_raw(wx, wy)
    landmarks[LANDMARK_INDEX_MCP] = to_raw(p_index[0], p_index[1])
    landmarks[LANDMARK_MIDDLE_MCP] = to_raw(p_middle[0], p_middle[1])
    landmarks[LANDMARK_RING_MCP] = to_raw(p_ring[0], p_ring[1])
    landmarks[LANDMARK_PINKY_MCP] = to_raw(p_pinky[0], p_pinky[1])

    return {
        "landmarks": landmarks,
        "gesture": gesture,
        "confidence": confidence,
        "width": width,
        "height": height,
    }
