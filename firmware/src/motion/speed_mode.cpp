/**
 * @file speed_mode.cpp
 * @brief Speed mode scaling implementation (Turbo / Precision modes).
 */

#include "motion/speed_mode.h"
#include <math.h>

static inline int8_t clamp_i8(int val) {
    if (val > 100) return 100;
    if (val < -100) return -100;
    return (int8_t)val;
}

SpeedMode getActiveSpeedMode(uint8_t flags) {
    // If both flags are set, precision (conservative safety choice) wins
    if (flags & MOTION_FLAG_PRECISION) {
        return SPEED_MODE_PRECISION;
    }
    if (flags & MOTION_FLAG_TURBO) {
        return SPEED_MODE_TURBO;
    }
    return SPEED_MODE_NORMAL;
}

const char* getSpeedModeName(uint8_t flags) {
    SpeedMode mode = getActiveSpeedMode(flags);
    switch (mode) {
        case SPEED_MODE_TURBO:     return "TURBO";
        case SPEED_MODE_PRECISION: return "PRECISE";
        default:                   return "";
    }
}

MotionCommand applySpeedMode(MotionCommand cmd, uint8_t flags) {
    SpeedMode mode = getActiveSpeedMode(flags);
    float scale = 1.0f;

    switch (mode) {
        case SPEED_MODE_PRECISION:
            scale = PRECISION_SCALE_FACTOR;
            break;
        case SPEED_MODE_TURBO:
            scale = TURBO_SCALE_FACTOR;
            break;
        case SPEED_MODE_NORMAL:
        default:
            return cmd;
    }

    int scaled_linear = (int)roundf((float)cmd.linear * scale);
    int scaled_angular = (int)roundf((float)cmd.angular * scale);

    MotionCommand out;
    out.linear = clamp_i8(scaled_linear);
    out.angular = clamp_i8(scaled_angular);
    return out;
}
