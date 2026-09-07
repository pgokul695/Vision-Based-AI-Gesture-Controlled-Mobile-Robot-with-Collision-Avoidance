/**
 * @file collision_filter.cpp
 * @brief Safety arbiter filtering incoming motion commands against onboard obstacle sensors.
 */

#include "motion/collision_filter.h"
#include <string.h>

static CollisionFilterConfig g_config = {
    US_SLOWDOWN_DIST_CM,
    US_STOP_DIST_CM,
    PACKET_TIMEOUT_MS,
    US_READING_MAX_AGE_MS
};

void collision_filter_init(const CollisionFilterConfig *config) {
    if (config) {
        g_config = *config;
    }
}

void collision_filter_process(
    const MotionPacket *raw_cmd,
    uint32_t packet_age_ms,
    const UltrasonicArrayReadings *us_data,
    const IRReadings *ir_data,
    uint32_t current_time_ms,
    SafeMotionOutput *out_motion
) {
    if (!out_motion) {
        return;
    }

    memset(out_motion, 0, sizeof(SafeMotionOutput));

    // Rule 1: Failsafe Timeout (>400ms packet silence)
    if (packet_age_ms > g_config.packet_timeout_ms || raw_cmd == NULL) {
        out_motion->linear = 0;
        out_motion->angular = 0;
        out_motion->timeout_active = true;
        return;
    }

    // Rule 2: E-Stop flag
    if (raw_cmd->flags & MOTION_FLAG_ESTOP) {
        out_motion->linear = 0;
        out_motion->angular = 0;
        out_motion->estop_active = true;
        return;
    }

    // Start with raw commanded values
    int8_t safe_linear = raw_cmd->linear;
    int8_t safe_angular = raw_cmd->angular;

    // Rule 3: Front Zone Check (Ultrasonic + IR)
    // Front IR hard stop
    if (ir_data && (ir_data->front_left_triggered || ir_data->front_right_triggered)) {
        if (safe_linear > 0) {
            safe_linear = 0;
            out_motion->front_blocked = true;
        }
    }

    // Front Ultrasonic proportional slowdown
    if (us_data && safe_linear > 0) {
        // Evaluate closest valid front reading across left, center, right
        float min_dist_cm = 999.0f;

        if (us_data->center.valid && (current_time_ms - us_data->center.timestamp_ms) <= g_config.max_sensor_age_ms) {
            if (us_data->center.distance_cm < min_dist_cm) {
                min_dist_cm = us_data->center.distance_cm;
            }
        }
        if (us_data->left.valid && (current_time_ms - us_data->left.timestamp_ms) <= g_config.max_sensor_age_ms) {
            if (us_data->left.distance_cm < min_dist_cm) {
                min_dist_cm = us_data->left.distance_cm;
            }
        }
        if (us_data->right.valid && (current_time_ms - us_data->right.timestamp_ms) <= g_config.max_sensor_age_ms) {
            if (us_data->right.distance_cm < min_dist_cm) {
                min_dist_cm = us_data->right.distance_cm;
            }
        }

        if (min_dist_cm <= g_config.us_stop_distance_cm) {
            safe_linear = 0;
            out_motion->front_blocked = true;
        } else if (min_dist_cm < g_config.us_slowdown_distance_cm) {
            // Proportional scaling factor between stop_dist and slowdown_dist
            float scale = (min_dist_cm - g_config.us_stop_distance_cm) /
                          (g_config.us_slowdown_distance_cm - g_config.us_stop_distance_cm);
            if (scale < 0.0f) scale = 0.0f;
            if (scale > 1.0f) scale = 1.0f;
            safe_linear = (int8_t)(safe_linear * scale);
            out_motion->front_blocked = true;
        }
    }

    // Rule 4: Side Zones (IR Binary Gate)
    // Left turn gate: prohibit angular < 0 (left) if side-left is tripped
    if (ir_data && ir_data->side_left_triggered) {
        if (safe_angular < 0) {
            safe_angular = 0;
            out_motion->side_left_blocked = true;
        }
    }

    // Right turn gate: prohibit angular > 0 (right) if side-right is tripped
    if (ir_data && ir_data->side_right_triggered) {
        if (safe_angular > 0) {
            safe_angular = 0;
            out_motion->side_right_blocked = true;
        }
    }

    // Rule 5: Rear Zone (IR Binary Gate)
    // Reverse gate: prohibit linear < 0 if rear-center is tripped
    if (ir_data && ir_data->rear_center_triggered) {
        if (safe_linear < 0) {
            safe_linear = 0;
            out_motion->rear_blocked = true;
        }
    }

    out_motion->linear = safe_linear;
    out_motion->angular = safe_angular;

    // TODO: Add sensor hysteresis to prevent rapid oscillating motor jerks near boundary thresholds
}
