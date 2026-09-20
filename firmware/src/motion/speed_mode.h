/**
 * @file speed_mode.h
 * @brief Speed mode scaling interface (Turbo / Precision modes).
 */

#ifndef SPEED_MODE_H
#define SPEED_MODE_H

#include <stdint.h>
#include <stdbool.h>
#include "motion/collision_filter.h"
#include "motion_packet.h"

#ifdef __cplusplus
extern "C" {
#endif

#define TURBO_SCALE_FACTOR     1.3f
#define PRECISION_SCALE_FACTOR 0.5f

typedef enum {
    SPEED_MODE_NORMAL = 0,
    SPEED_MODE_TURBO,
    SPEED_MODE_PRECISION
} SpeedMode;

/**
 * @brief Determines the active speed mode based on packet flags.
 * If both TURBO and PRECISION flags are present, PRECISION wins (conservative safety choice).
 */
SpeedMode getActiveSpeedMode(uint8_t flags);

/**
 * @brief Returns short display string for the active speed mode ("TURBO", "PREC", or "").
 */
const char* getSpeedModeName(uint8_t flags);

/**
 * @brief Applies speed mode scaling factor to incoming command before collision filtering.
 *
 * @param cmd Raw commanded motion.
 * @param flags Packet flag bitmask.
 * @return Scaled motion command, clamped to [-100, 100].
 */
MotionCommand applySpeedMode(MotionCommand cmd, uint8_t flags);

#ifdef __cplusplus
}
#endif

#endif // SPEED_MODE_H
