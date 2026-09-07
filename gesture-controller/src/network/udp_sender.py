"""UDP socket sender interface for dispatching MotionPackets to ESP32."""

import socket
import sys
from pathlib import Path
from typing import Optional

# Ensure protocol package is importable from repository root
repo_root = Path(__file__).resolve().parent.parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from protocol.motion_packet import (
    MotionPacket,
    FLAG_ESTOP,
    FLAG_LOW_CONFIDENCE,
)


class UdpSender:
    """Manages UDP transmission of MotionPackets to the robot ESP32."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8888, **kwargs) -> None:
        """Initialize socket destination and sequence tracker.

        Supports both (host, port) and legacy (robot_ip, robot_port).
        """
        self.host = kwargs.get("robot_ip", host)
        self.port = kwargs.get("robot_port", port)
        self._seq: int = 0
        self._socket: Optional[socket.socket] = None

    def start(self) -> None:
        """Open client UDP socket."""
        if self._socket is None:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(
        self,
        linear: int,
        angular: int,
        estop: bool = False,
        low_confidence: bool = False,
    ) -> int:
        """Packs a MotionPacket with the current sequence number and transmits it over UDP.

        Args:
            linear: -100 to 100 percentage forward/reverse speed.
            angular: -100 to 100 percentage turn rate.
            estop: Emergency stop flag.
            low_confidence: Low tracking confidence flag.

        Returns:
            Number of bytes transmitted (always 10 for a valid packet).
        """
        if self._socket is None:
            self.start()

        flags = 0
        if estop:
            flags |= FLAG_ESTOP
        if low_confidence:
            flags |= FLAG_LOW_CONFIDENCE

        pkt = MotionPacket(
            seq=self._seq,
            linear=int(linear),
            angular=int(angular),
            flags=flags,
        )

        payload = pkt.to_bytes()
        bytes_sent = self._socket.sendto(payload, (self.host, self.port))

        self._seq = (self._seq + 1) % 65536
        return bytes_sent

    # Alias for backward compatibility
    def send_motion(
        self,
        linear: int,
        angular: int,
        is_estop: bool = False,
        is_low_confidence: bool = False,
    ) -> int:
        """Backward-compatible alias for send()."""
        return self.send(
            linear=linear,
            angular=angular,
            estop=is_estop,
            low_confidence=is_low_confidence,
        )

    def close(self) -> None:
        """Closes the UDP socket."""
        if self._socket is not None:
            self._socket.close()
            self._socket = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
