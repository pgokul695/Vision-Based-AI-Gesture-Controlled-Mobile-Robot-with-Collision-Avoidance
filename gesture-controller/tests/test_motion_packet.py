"""Unit tests for MotionPacket protocol serialization and flag extensions."""

import sys
from pathlib import Path
import pytest

repo_root = Path(__file__).resolve().parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

protocol_dir = repo_root / "protocol"
if str(protocol_dir) not in sys.path:
    sys.path.insert(0, str(protocol_dir))

from motion_packet import (
    MotionPacket,
    pack_motion_packet,
    unpack_motion_packet,
    FLAG_ESTOP,
    FLAG_LOW_CONFIDENCE,
    FLAG_FUN_TRICK,
    FLAG_TURBO,
    FLAG_PRECISION,
    MOTION_PACKET_MAGIC,
    MOTION_PACKET_VERSION,
)


def test_motion_packet_fun_trick_flag():
    """Verify FLAG_FUN_TRICK serialization and property check."""
    pkt = MotionPacket(seq=10, linear=0, angular=80, flags=FLAG_FUN_TRICK)
    assert pkt.is_fun_trick is True
    assert pkt.is_estop is False
    assert pkt.is_low_confidence is False

    raw = pkt.to_bytes()
    assert len(raw) == 10

    unpacked = MotionPacket.from_bytes(raw)
    assert unpacked.seq == 10
    assert unpacked.linear == 0
    assert unpacked.angular == 80
    assert unpacked.flags == FLAG_FUN_TRICK
    assert unpacked.is_fun_trick is True


def test_motion_packet_combined_flags():
    """Verify multiple flags combined with bitwise OR."""
    flags = FLAG_ESTOP | FLAG_FUN_TRICK
    pkt = MotionPacket(seq=1, flags=flags)
    assert pkt.is_estop is True
    assert pkt.is_fun_trick is True
    assert pkt.is_low_confidence is False

    raw = pkt.to_bytes()
    unpacked = unpack_motion_packet(raw)
    assert unpacked.is_estop is True
    assert unpacked.is_fun_trick is True


def test_motion_packet_invalid_length():
    """Verify rejection of undersized or oversized binary frames."""
    with pytest.raises(ValueError, match="Packet size mismatch"):
        MotionPacket.from_bytes(b"\xA5\x01\x00\x01")

    with pytest.raises(ValueError, match="Packet size mismatch"):
        MotionPacket.from_bytes(b"\xA5" * 12)


def test_motion_packet_invalid_magic():
    """Verify rejection of corrupted magic byte."""
    bad_magic = b"\xFF\x01\x00\x01\x00\x00\x00\x00\x00\x00"
    with pytest.raises(ValueError, match="Invalid magic byte"):
        MotionPacket.from_bytes(bad_magic)


def test_motion_packet_speed_mode_flags():
    """Verify FLAG_TURBO and FLAG_PRECISION serialization and property checks."""
    # Turbo
    pkt_turbo = MotionPacket(seq=5, linear=50, angular=0, flags=FLAG_TURBO)
    assert pkt_turbo.is_turbo is True
    assert pkt_turbo.is_precision is False
    raw_turbo = pkt_turbo.to_bytes()
    assert MotionPacket.from_bytes(raw_turbo).is_turbo is True

    # Precision
    pkt_prec = MotionPacket(seq=6, linear=50, angular=0, flags=FLAG_PRECISION)
    assert pkt_prec.is_precision is True
    assert pkt_prec.is_turbo is False
    raw_prec = pkt_prec.to_bytes()
    assert MotionPacket.from_bytes(raw_prec).is_precision is True


def test_motion_packet_turbo_precision_conflict():
    """Verify packet with both turbo and precision flags."""
    pkt = MotionPacket(seq=7, flags=FLAG_TURBO | FLAG_PRECISION)
    assert pkt.is_turbo is True
    assert pkt.is_precision is True
