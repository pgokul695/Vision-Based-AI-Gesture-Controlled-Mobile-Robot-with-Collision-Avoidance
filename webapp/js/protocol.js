/**
 * @file protocol.js
 * @brief JavaScript implementation of the 10-byte binary MotionPacket protocol.
 *
 * Synchronized with protocol/motion_packet.h and protocol/motion_packet.py.
 */

export const MOTION_PACKET_MAGIC = 0xA5;
export const MOTION_PACKET_VERSION = 1;
export const MOTION_PACKET_SIZE = 10;

// Flag bitmasks matching firmware definitions
export const FLAG_ESTOP          = 0x01; // Bit 0: Emergency stop
export const FLAG_LOW_CONFIDENCE = 0x02; // Bit 1: Low confidence gesture detection
export const FLAG_FUN_TRICK      = 0x04; // Bit 2: Fun trick activation (canned spin)
export const FLAG_TURBO          = 0x08; // Bit 3: Turbo speed mode (1.3x)
export const FLAG_PRECISION      = 0x10; // Bit 4: Precision speed mode (0.5x)

/**
 * Packs motion values into a 10-byte binary payload (DataView, little-endian).
 *
 * Byte layout:
 * [0]   magic    (uint8)  = 0xA5
 * [1]   version  (uint8)  = 1
 * [2-3] seq      (uint16) = Sequence counter (little-endian)
 * [4]   linear   (int8)   = -100..100 %
 * [5]   angular  (int8)   = -100..100 %
 * [6]   flags    (uint8)  = Bitfield
 * [7-9] reserved (uint8[3]) = 0x00, 0x00, 0x00
 *
 * @param {Object} params
 * @param {number} params.seq
 * @param {number} params.linear
 * @param {number} params.angular
 * @param {number} [params.flags=0]
 * @returns {Uint8Array} 10-byte binary array
 */
export function packMotionPacket({ seq = 0, linear = 0, angular = 0, flags = 0 }) {
    const buffer = new ArrayBuffer(MOTION_PACKET_SIZE);
    const view = new DataView(buffer);

    // Clamping values to valid ranges
    const clampedLinear = Math.max(-100, Math.min(100, Math.round(linear)));
    const clampedAngular = Math.max(-100, Math.min(100, Math.round(angular)));
    const uint16Seq = (seq >>> 0) & 0xFFFF;
    const uint8Flags = (flags >>> 0) & 0xFF;

    view.setUint8(0, MOTION_PACKET_MAGIC);
    view.setUint8(1, MOTION_PACKET_VERSION);
    view.setUint16(2, uint16Seq, true); // little-endian
    view.setInt8(4, clampedLinear);
    view.setInt8(5, clampedAngular);
    view.setUint8(6, uint8Flags);
    view.setUint8(7, 0x00);
    view.setUint8(8, 0x00);
    view.setUint8(9, 0x00);

    return new Uint8Array(buffer);
}

/**
 * Validates and unpacks a 10-byte binary MotionPacket.
 *
 * @param {ArrayBuffer|Uint8Array} data
 * @returns {Object} Unpacked packet fields
 */
export function unpackMotionPacket(data) {
    const buffer = data.buffer ? data.buffer.slice(data.byteOffset, data.byteOffset + data.byteLength) : data;
    if (buffer.byteLength !== MOTION_PACKET_SIZE) {
        throw new Error(`Packet size mismatch: expected ${MOTION_PACKET_SIZE}, got ${buffer.byteLength}`);
    }

    const view = new DataView(buffer);
    const magic = view.getUint8(0);
    const version = view.getUint8(1);

    if (magic !== MOTION_PACKET_MAGIC) {
        throw new Error(`Invalid magic byte: expected 0x${MOTION_PACKET_MAGIC.toString(16)}, got 0x${magic.toString(16)}`);
    }
    if (version !== MOTION_PACKET_VERSION) {
        throw new Error(`Unsupported version: expected ${MOTION_PACKET_VERSION}, got ${version}`);
    }

    const seq = view.getUint16(2, true);
    const linear = view.getInt8(4);
    const angular = view.getInt8(5);
    const flags = view.getUint8(6);

    return {
        seq,
        linear,
        angular,
        flags,
        isEstop: Boolean(flags & FLAG_ESTOP),
        isLowConfidence: Boolean(flags & FLAG_LOW_CONFIDENCE),
        isFunTrick: Boolean(flags & FLAG_FUN_TRICK),
        isTurbo: Boolean(flags & FLAG_TURBO),
        isPrecision: Boolean(flags & FLAG_PRECISION),
    };
}
