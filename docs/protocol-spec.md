# Motion Control Protocol Specification

This document defines the binary packet protocol used to send real-time motion commands from the host controller (laptop running gesture detection) to the mobile robot firmware (ESP32) over UDP.

## 1. Transport Overview

- **Protocol**: UDP (User Datagram Protocol) over standard Wi-Fi (802.11 b/g/n)
- **Format**: Fixed-length packed binary structure (no JSON or text-based framing)
- **Endianness**: Little-endian (`<` in Python `struct`, standard ESP32 / x86 native byte order)
- **Packet Size**: Exactly 10 bytes
- **Transmission Rate**: Typically 20 Hz to 50 Hz (synchronized with camera frame rate)

---

## 2. Packet Binary Layout

| Byte Offset | Field Name | Type | Size (Bytes) | Range / Value | Description |
|-------------|------------|------|--------------|---------------|-------------|
| `0` | `magic` | `uint8_t` | 1 | `0xA5` | Sanity check byte to reject malformed/unrelated packets |
| `1` | `version` | `uint8_t` | 1 | `1` | Protocol version; increments on breaking changes |
| `2 - 3` | `seq` | `uint16_t` | 2 | `0 - 65535` | Incrementing sequence counter (detects stale / out-of-order packets) |
| `4` | `linear` | `int8_t` | 1 | `-100 .. 100` | Commanded forward/backward speed percentage (-100 = full reverse, +100 = full forward) |
| `5` | `angular` | `int8_t` | 1 | `-100 .. 100` | Commanded turn rate percentage (-100 = full left/CCW, +100 = full right/CW) |
| `6` | `flags` | `uint8_t` | 1 | Bitfield | Control status and emergency stop flags |
| `7 - 9` | `reserved` | `uint8_t[3]` | 3 | `0x00, 0x00, 0x00` | Padding for future extensions (gesture ID, drive modes, etc.) |

**Total Size**: Exactly 10 bytes (`sizeof(MotionPacket) == 10`).

---

## 3. Flags Bitmask (`flags`)

The `flags` byte provides single-bit status indicators:

| Bit Index | Mask | Name | Description |
|-----------|------|------|-------------|
| `Bit 0` | `0x01` | `FLAG_ESTOP` | Emergency Stop request from host. ESP32 halts motors immediately when set. |
| `Bit 1` | `0x02` | `FLAG_LOW_CONFIDENCE` | Host hand tracking confidence is degraded. ESP32 may apply conservative velocity caps. |
| `Bits 2-7`| `0xFC` | `RESERVED` | Reserved for future flag allocations. Must be transmitted as `0`. |

---

## 4. Versioning Policy

1. **Protocol Version Field (`version`)**: Initial baseline version is `1`.
2. **Breaking Changes**:
   - Any modification to existing field sizes, offsets, endianness, or meaning requires incrementing `version` by +1 (e.g., `version = 2`).
   - The ESP32 receiver will reject any packet whose `version` does not match its supported protocol version.
3. **Non-Breaking Extensions**:
   - Non-breaking enhancements MUST utilize the 3-byte `reserved` field (bytes 7-9) or unused bits in `flags` (bits 2-7).
   - Receivers ignoring extended fields continue to operate reliably.

---

## 5. Receiver Safety & Timeout Policy

The mobile robot relies on constant communication keep-alive from the host:

- **400 ms Failsafe Stop**:
  - The ESP32 firmware monitors elapsed time since the last valid received `MotionPacket`.
  - If no valid packet arrives within **400 ms**, the robot must immediately zero the commanded velocity (`linear = 0, angular = 0`).
  - This prevents runaway situations caused by Wi-Fi drops, laptop application crashes, or UDP packet loss.
- **Packet Validation**:
  - A packet is valid if and only if:
    1. Datagram payload length is exactly 10 bytes.
    2. `magic == 0xA5`.
    3. `version == 1`.
  - Packets failing validation are discarded immediately without modifying motor state.
- **Sequence Tracking**:
  - If a received packet's `seq` is older than the highest observed `seq` (accounting for 16-bit wrap-around), it is classified as out-of-order and dropped.

---

## 6. Code Reference

- C/C++ Header: [protocol/motion_packet.h](file:///home/gokul/Project/Vision-Based-AI-Gesture-Controlled-Mobile-Robot-with-Collision-Avoidance/protocol/motion_packet.h)
- Python Module: [protocol/motion_packet.py](file:///home/gokul/Project/Vision-Based-AI-Gesture-Controlled-Mobile-Robot-with-Collision-Avoidance/protocol/motion_packet.py)
