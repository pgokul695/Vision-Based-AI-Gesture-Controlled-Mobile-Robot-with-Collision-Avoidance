"""Motion packet protocol definition for gesture controller.

NOTE: Synchronized with protocol/motion_packet.h.
If modifying this file, you MUST update protocol/motion_packet.h to match!
"""

from dataclasses import dataclass, field
import struct
from typing import ClassVar

MOTION_PACKET_MAGIC: int = 0xA5
MOTION_PACKET_VERSION: int = 1

# Flag bitmasks (flags byte)
FLAG_ESTOP: int = 1 << 0           # Bit 0: Emergency stop
FLAG_LOW_CONFIDENCE: int = 1 << 1  # Bit 1: Low confidence gesture detection


@dataclass
class MotionPacket:
    """10-byte packed binary motion packet transmitted over UDP.

    Layout (<BBHbbB3s):
    - magic: uint8 (0xA5)
    - version: uint8 (1)
    - seq: uint16 (incrementing counter)
    - linear: int8 (-100..100 % forward/backward)
    - angular: int8 (-100..100 % turn rate)
    - flags: uint8 (bit0=estop, bit1=low_conf, bits2-7=reserved)
    - reserved: bytes (3 bytes padding / future extension)
    """

    seq: int = 0
    linear: int = 0
    angular: int = 0
    flags: int = 0
    reserved: bytes = field(default_factory=lambda: b"\x00\x00\x00")
    magic: int = MOTION_PACKET_MAGIC
    version: int = MOTION_PACKET_VERSION

    # struct format string:
    # < = little-endian
    # B = uint8 (magic)
    # B = uint8 (version)
    # H = uint16 (seq)
    # b = int8 (linear)
    # b = int8 (angular)
    # B = uint8 (flags)
    # 3s = 3-byte char array / bytes (reserved)
    FORMAT: ClassVar[str] = "<BBHbbB3s"
    SIZE: ClassVar[int] = struct.calcsize(FORMAT)

    def __post_init__(self) -> None:
        if len(self.reserved) != 3:
            raise ValueError(f"reserved must be exactly 3 bytes, got {len(self.reserved)}")
        if not (-100 <= self.linear <= 100):
            raise ValueError(f"linear must be in range [-100, 100], got {self.linear}")
        if not (-100 <= self.angular <= 100):
            raise ValueError(f"angular must be in range [-100, 100], got {self.angular}")
        if not (0 <= self.flags <= 255):
            raise ValueError(f"flags must be uint8 [0, 255], got {self.flags}")
        if not (0 <= self.seq <= 65535):
            raise ValueError(f"seq must be uint16 [0, 65535], got {self.seq}")

    @property
    def is_estop(self) -> bool:
        """Returns True if emergency stop flag bit is set."""
        return bool(self.flags & FLAG_ESTOP)

    @property
    def is_low_confidence(self) -> bool:
        """Returns True if low confidence flag bit is set."""
        return bool(self.flags & FLAG_LOW_CONFIDENCE)

    def to_bytes(self) -> bytes:
        """Serialize packet to 10-byte packed binary payload."""
        return struct.pack(
            self.FORMAT,
            self.magic,
            self.version,
            self.seq,
            self.linear,
            self.angular,
            self.flags,
            self.reserved,
        )

    @classmethod
    def from_bytes(cls, data: bytes) -> "MotionPacket":
        """Deserialize and validate a 10-byte binary payload.

        Raises:
            ValueError: If buffer size is invalid, magic mismatch, or version mismatch.
        """
        if len(data) != cls.SIZE:
            raise ValueError(f"Packet size mismatch: expected {cls.SIZE} bytes, got {len(data)}")

        magic, version, seq, linear, angular, flags, reserved = struct.unpack(cls.FORMAT, data)

        if magic != MOTION_PACKET_MAGIC:
            raise ValueError(f"Invalid magic byte: expected 0x{MOTION_PACKET_MAGIC:02X}, got 0x{magic:02X}")
        if version != MOTION_PACKET_VERSION:
            raise ValueError(f"Unsupported protocol version: expected {MOTION_PACKET_VERSION}, got {version}")

        return cls(
            seq=seq,
            linear=linear,
            angular=angular,
            flags=flags,
            reserved=reserved,
            magic=magic,
            version=version,
        )


def pack_motion_packet(
    seq: int,
    linear: int,
    angular: int,
    flags: int = 0,
    reserved: bytes = b"\x00\x00\x00",
) -> bytes:
    """Helper function to pack a motion packet into bytes directly."""
    pkt = MotionPacket(
        seq=seq,
        linear=linear,
        angular=angular,
        flags=flags,
        reserved=reserved,
    )
    return pkt.to_bytes()


def unpack_motion_packet(data: bytes) -> MotionPacket:
    """Helper function to unpack and validate a motion packet from bytes."""
    return MotionPacket.from_bytes(data)
