/**
 * @file motion_packet.h
 * @brief 10-byte packed binary UDP motion packet definition for firmware.
 *
 * NOTE: Synchronized with protocol/motion_packet.py.
 * If modifying this file, you MUST update protocol/motion_packet.py to match!
 */

#ifndef MOTION_PACKET_H
#define MOTION_PACKET_H

#include <stdint.h>
#include <stddef.h>
#include <string.h>

#ifdef __cplusplus
extern "C" {
#endif

#define MOTION_PACKET_MAGIC       0xA5
#define MOTION_PACKET_VERSION     1

// Flag bit masks (flags field)
#define MOTION_FLAG_ESTOP         (1 << 0)  // Bit 0: Emergency stop
#define MOTION_FLAG_LOW_CONFIDENCE (1 << 1) // Bit 1: Low confidence gesture
// Bits 2-7: Reserved for future flag usage

/**
 * @brief 10-byte packed binary motion packet transmitted over UDP.
 *
 * Byte layout (little-endian):
 * [0]   magic    (uint8_t)  - Fixed 0xA5
 * [1]   version  (uint8_t)  - Protocol version (1)
 * [2-3] seq      (uint16_t) - Little-endian sequence counter
 * [4]   linear   (int8_t)   - Linear speed (-100 to 100 %)
 * [5]   angular  (int8_t)   - Angular turn rate (-100 to 100 %)
 * [6]   flags    (uint8_t)  - Bitfield: bit0=estop, bit1=low_conf
 * [7-9] reserved (uint8_t[3])- 3 bytes padding/future fields
 */
#pragma pack(push, 1)
struct MotionPacket {
    uint8_t  magic;        // Fixed 0xA5
    uint8_t  version;      // Protocol version, starts at 1
    uint16_t seq;          // Sequence counter (little-endian)
    int8_t   linear;       // -100..100 forward/backward %
    int8_t   angular;      // -100..100 turn rate %
    uint8_t  flags;        // Bit 0: estop, Bit 1: low_confidence
    uint8_t  reserved[3];  // Future expansion / alignment padding
} __attribute__((packed));
#pragma pack(pop)

typedef struct MotionPacket MotionPacket;

// Compile-time sanity check that size is strictly 10 bytes
#if defined(__cplusplus)
static_assert(sizeof(MotionPacket) == 10, "MotionPacket must be exactly 10 bytes");
#endif

/**
 * @brief Validates magic byte and version of a MotionPacket.
 *
 * @param pkt Reference or pointer to MotionPacket to validate.
 * @return true if magic == 0xA5 and version == 1, false otherwise.
 */
static inline bool is_valid_motion_packet(const MotionPacket *pkt) {
    if (pkt == NULL) {
        return false;
    }
    return (pkt->magic == MOTION_PACKET_MAGIC) && (pkt->version == MOTION_PACKET_VERSION);
}

/**
 * @brief Alias for is_valid_motion_packet.
 */
static inline bool motion_packet_is_valid(const MotionPacket *pkt) {
    return is_valid_motion_packet(pkt);
}

/**
 * @brief Validates raw bytes and unpacks into a MotionPacket struct.
 *
 * @param buffer Pointer to raw received byte buffer.
 * @param len Length of received buffer.
 * @param out_pkt Pointer to output MotionPacket struct.
 * @return true if len == sizeof(MotionPacket) and validation passes.
 */
static inline bool parse_motion_packet(const uint8_t *buffer, size_t len, MotionPacket *out_pkt) {
    if (buffer == NULL || out_pkt == NULL || len != sizeof(MotionPacket)) {
        return false;
    }
    memcpy(out_pkt, buffer, sizeof(MotionPacket));
    return is_valid_motion_packet(out_pkt);
}

#ifdef __cplusplus
}
#endif

#endif // MOTION_PACKET_H
