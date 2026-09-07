"""Unit tests for hand tracker and gesture controller components."""

import pytest
import sys
from pathlib import Path

# Add project source paths
test_dir = Path(__file__).resolve().parent
gc_src = test_dir.parent / "src"
repo_root = test_dir.parent.parent

sys.path.insert(0, str(gc_src))
sys.path.insert(0, str(repo_root))

from gesture.hand_tracker import HandTracker, HandTrackingResult
from network.udp_sender import UdpSender
from protocol.motion_packet import (
    MotionPacket,
    MOTION_PACKET_MAGIC,
    MOTION_PACKET_VERSION,
    FLAG_ESTOP,
    FLAG_LOW_CONFIDENCE,
)


def test_hand_tracking_result_defaults():
    """Verify HandTrackingResult initial default values."""
    res = HandTrackingResult()
    assert res.landmarks is None
    assert res.gesture is None
    assert res.gesture_confidence == 0.0


def test_hand_tracker_missing_model_raises_filenotfound():
    """Verify HandTracker raises a descriptive FileNotFoundError when model task is missing."""
    with pytest.raises(FileNotFoundError, match="MediaPipe GestureRecognizer model file not found"):
        HandTracker(model_path="/non/existent/path/gesture_recognizer.task")


def test_udp_sender_sequence_increment():
    """Verify UdpSender increments sequence numbers and sets flags correctly."""
    sender = UdpSender(host="127.0.0.1", port=9999)
    assert sender._seq == 0

    # Sending without listening socket in UDP is non-blocking
    bytes_sent = sender.send(linear=50, angular=-20, estop=False, low_confidence=False)
    assert bytes_sent == 10
    assert sender._seq == 1

    bytes_sent = sender.send(linear=0, angular=0, estop=True, low_confidence=False)
    assert bytes_sent == 10
    assert sender._seq == 2

    sender.close()


def test_motion_packet_roundtrip_values():
    """Verify MotionPacket serialization matches expected binary size and values."""
    pkt = MotionPacket(
        seq=500,
        linear=85,
        angular=-45,
        flags=FLAG_ESTOP,
    )
    raw = pkt.to_bytes()
    assert len(raw) == 10
    assert raw[0] == MOTION_PACKET_MAGIC
    assert raw[1] == MOTION_PACKET_VERSION

    unpacked = MotionPacket.from_bytes(raw)
    assert unpacked.seq == 500
    assert unpacked.linear == 85
    assert unpacked.angular == -45
    assert unpacked.is_estop is True
    assert unpacked.is_low_confidence is False


def test_motion_packet_invalid_bytes():
    """Verify MotionPacket rejects invalid magic, size, and version."""
    with pytest.raises(ValueError, match="Packet size mismatch"):
        MotionPacket.from_bytes(b"\x00" * 9)

    valid_bytes = bytearray(MotionPacket().to_bytes())
    valid_bytes[0] = 0x00  # Corrupt magic byte
    with pytest.raises(ValueError, match="Invalid magic byte"):
        MotionPacket.from_bytes(bytes(valid_bytes))

    valid_bytes = bytearray(MotionPacket().to_bytes())
    valid_bytes[1] = 99  # Unsupported version
    with pytest.raises(ValueError, match="Unsupported protocol version"):
        MotionPacket.from_bytes(bytes(valid_bytes))
