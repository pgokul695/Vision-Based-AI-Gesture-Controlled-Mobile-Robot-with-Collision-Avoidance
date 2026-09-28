"""Deterministic synthetic hand landmark generator for testing gesture pipelines."""

import math
from typing import Any, Dict, List, Optional, Tuple

LANDMARK_WRIST = 0
LANDMARK_INDEX_MCP = 5
LANDMARK_INDEX_PIP = 6
LANDMARK_INDEX_DIP = 7
LANDMARK_INDEX_TIP = 8

LANDMARK_MIDDLE_MCP = 9
LANDMARK_MIDDLE_PIP = 10
LANDMARK_MIDDLE_DIP = 11
LANDMARK_MIDDLE_TIP = 12

LANDMARK_RING_MCP = 13
LANDMARK_RING_PIP = 14
LANDMARK_RING_DIP = 15
LANDMARK_RING_TIP = 16

LANDMARK_PINKY_MCP = 17
LANDMARK_PINKY_PIP = 18
LANDMARK_PINKY_DIP = 19
LANDMARK_PINKY_TIP = 20


def make_hand(
    cx: float = 0.5,
    cy: float = 0.5,
    scale: float = 80.0,
    tilt_deg: float = 0.0,
    gesture: Optional[str] = "Open_Palm",
    confidence: float = 0.9,
    width: float = 640.0,
    height: float = 480.0,
    curled: Optional[bool] = None,
) -> Dict[str, Any]:
    """Generates a synthetic frame with all 21 MediaPipe landmarks.

    Args:
        cx: Normalized user-space center X of palm (0.0=left, 1.0=right).
        cy: Normalized center Y of palm (0.0=top, 1.0=bottom).
        scale: Hand scale in pixels (wrist to middle knuckle).
        tilt_deg: Tilt angle in degrees (-90 to +90, positive = tilted to user's right).
        gesture: MediaPipe classified gesture name (e.g. Open_Palm, Closed_Fist).
        confidence: Gesture classification confidence [0.0, 1.0].
        width: Frame width in pixels.
        height: Frame height in pixels.
        curled: Explicitly curl fingers (fist) if True, or extend if False. Defaults based on gesture.

    Returns:
        Frame dictionary compatible with GesturePipeline.step(frame, t_ms).
    """
    if gesture is None and curled is None:
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

    # Unit axis vector along hand: points from wrist toward fingers
    # In screen coordinates, upwards is -y, so upright has (0, -1)
    ax = sin_t
    ay = -cos_t

    # Perpendicular unit vector (towards user's right hand side)
    ux = cos_t
    uy = sin_t

    # Wrist position: K - scale * a
    wx = kx - scale * ax
    wy = ky - scale * ay

    # Determine finger curl: fist if Closed_Fist or curled=True
    is_fist = (gesture == "Closed_Fist") if (curled is None) else bool(curled)

    # Lateral offsets for the 4 fingers relative to knuckle centroid K
    finger_offsets = [
        (-0.30 * scale, LANDMARK_INDEX_MCP, LANDMARK_INDEX_PIP, LANDMARK_INDEX_DIP, LANDMARK_INDEX_TIP),
        (-0.10 * scale, LANDMARK_MIDDLE_MCP, LANDMARK_MIDDLE_PIP, LANDMARK_MIDDLE_DIP, LANDMARK_MIDDLE_TIP),
        (0.10 * scale, LANDMARK_RING_MCP, LANDMARK_RING_PIP, LANDMARK_RING_DIP, LANDMARK_RING_TIP),
        (0.30 * scale, LANDMARK_PINKY_MCP, LANDMARK_PINKY_PIP, LANDMARK_PINKY_DIP, LANDMARK_PINKY_TIP),
    ]

    pts = [(wx, wy)] * 21
    pts[LANDMARK_WRIST] = (wx, wy)

    for lat_offset, mcp_i, pip_i, dip_i, tip_i in finger_offsets:
        # Base MCP position at knuckle line
        mcp_x = kx + lat_offset * ux
        mcp_y = ky + lat_offset * uy
        pts[mcp_i] = (mcp_x, mcp_y)

        if is_fist:
            # Curled fingers: fingertips curl in towards palm (ratio ~ 1.05)
            pip_x = mcp_x + 0.15 * scale * ax
            pip_y = mcp_y + 0.15 * scale * ay
            dip_x = mcp_x + 0.12 * scale * ax
            dip_y = mcp_y + 0.12 * scale * ay
            tip_x = mcp_x + 0.08 * scale * ax
            tip_y = mcp_y + 0.08 * scale * ay
        else:
            # Extended fingers: fingertips reach outward (ratio ~ 1.80)
            pip_x = mcp_x + 0.30 * scale * ax
            pip_y = mcp_y + 0.30 * scale * ay
            dip_x = mcp_x + 0.55 * scale * ax
            dip_y = mcp_y + 0.55 * scale * ay
            tip_x = mcp_x + 0.80 * scale * ax
            tip_y = mcp_y + 0.80 * scale * ay

        pts[pip_i] = (pip_x, pip_y)
        pts[dip_i] = (dip_x, dip_y)
        pts[tip_i] = (tip_x, tip_y)

    # Convert user-space pixel coordinates to raw normalized coordinates
    # Pipeline inverts raw x: user_x = (1.0 - raw_x) * width -> raw_x = 1.0 - (user_x / width)
    landmarks: List[Tuple[float, float, float]] = []
    for px, py in pts:
        raw_x = 1.0 - (px / width)
        raw_y = py / height
        landmarks.append((round(raw_x, 6), round(raw_y, 6), 0.0))

    return {
        "landmarks": landmarks,
        "gesture": gesture,
        "confidence": confidence,
        "width": width,
        "height": height,
    }
