/**
 * @file collision_filter.cpp
 * @brief Safety arbiter filtering incoming motion commands against obstacle sensors.
 */

#include "motion/collision_filter.h"
#include <string.h>

static CollisionFilterState g_filter_state = { {0, 0}, false, false, false, false, false, false, false, 999.0f };

void collision_filter_init(void) {
    memset(&g_filter_state, 0, sizeof(CollisionFilterState));
    g_filter_state.min_front_dist_cm = 999.0f;
}

MotionCommand applyCollisionFilter(MotionCommand incoming) {
    int8_t lin = incoming.linear;
    int8_t ang = incoming.angular;

    // Reset intervention flags for this cycle
    g_filter_state.front_us_slowdown = false;
    g_filter_state.front_us_stop = false;
    g_filter_state.front_us_all_stale = false;
    g_filter_state.front_ir_blocked = false;
    g_filter_state.side_left_blocked = false;
    g_filter_state.side_right_blocked = false;
    g_filter_state.rear_blocked = false;
    g_filter_state.min_front_dist_cm = 999.0f;

    // =========================================================================
    // 1. FRONT ZONE (Ultrasonic array + Front IRs)
    // Affects POSITIVE (forward) linear motion only. Never blocks reverse.
    // =========================================================================
    float min_us_dist = 999.0f;
    uint8_t fresh_us_count = 0;

    // Check Front-Left US
    if (!ultrasonic_is_stale(US_POS_FRONT_LEFT)) {
        float d = getDistanceCm(US_POS_FRONT_LEFT);
        if (d > 0.0f) {
            fresh_us_count++;
            if (d < min_us_dist) min_us_dist = d;
        }
    }

    // Check Front-Center US
    if (!ultrasonic_is_stale(US_POS_FRONT_CENTER)) {
        float d = getDistanceCm(US_POS_FRONT_CENTER);
        if (d > 0.0f) {
            fresh_us_count++;
            if (d < min_us_dist) min_us_dist = d;
        }
    }

    // Check Front-Right US
    if (!ultrasonic_is_stale(US_POS_FRONT_RIGHT)) {
        float d = getDistanceCm(US_POS_FRONT_RIGHT);
        if (d > 0.0f) {
            fresh_us_count++;
            if (d < min_us_dist) min_us_dist = d;
        }
    }

    g_filter_state.min_front_dist_cm = min_us_dist;

    if (fresh_us_count == 0) {
        // FAIL TOWARD SAFETY: All 3 US sensors are stale or disconnected.
        // Treat as obstacle very close and prohibit forward motion.
        g_filter_state.front_us_all_stale = true;
        if (lin > 0) {
            lin = 0;
        }
    } else {
        if (min_us_dist <= US_STOP_DIST_CM) {
            // Hard stop threshold
            g_filter_state.front_us_stop = true;
            if (lin > 0) {
                lin = 0;
            }
        } else if (min_us_dist < US_SLOWDOWN_DIST_CM) {
            // Proportional slowdown between US_STOP_DIST_CM and US_SLOWDOWN_DIST_CM
            g_filter_state.front_us_slowdown = true;
            if (lin > 0) {
                float scale = (min_us_dist - US_STOP_DIST_CM) / (US_SLOWDOWN_DIST_CM - US_STOP_DIST_CM);
                if (scale < 0.0f) scale = 0.0f;
                if (scale > 1.0f) scale = 1.0f;
                lin = (int8_t)(lin * scale);
            }
        }
    }

    // Front IR reflex override (immediate hard stop for forward motion)
    if (isTriggered(IR_POS_FRONT_LEFT) || isTriggered(IR_POS_FRONT_RIGHT)) {
        g_filter_state.front_ir_blocked = true;
        if (lin > 0) {
            lin = 0;
        }
    }

    // =========================================================================
    // 2. SIDE ZONES (Side-Left & Side-Right IRs)
    // Binary turn gating. Does not affect linear speed.
    // Turn Left is angular < 0; Turn Right is angular > 0.
    // =========================================================================
    if (isTriggered(IR_POS_SIDE_LEFT)) {
        g_filter_state.side_left_blocked = true;
        if (ang < 0) {
            ang = 0;
        }
    }

    if (isTriggered(IR_POS_SIDE_RIGHT)) {
        g_filter_state.side_right_blocked = true;
        if (ang > 0) {
            ang = 0;
        }
    }

    // =========================================================================
    // 3. REAR ZONE (Rear-Center IR)
    // Prohibits reverse (linear < 0). Does not affect forward or angular.
    // =========================================================================
    if (isTriggered(IR_POS_REAR_CENTER)) {
        g_filter_state.rear_blocked = true;
        if (lin < 0) {
            lin = 0;
        }
    }

    g_filter_state.cmd.linear = lin;
    g_filter_state.cmd.angular = ang;

    return g_filter_state.cmd;
}

void collision_filter_get_state(CollisionFilterState *out_state) {
    if (out_state) {
        *out_state = g_filter_state;
    }
}

void collision_filter_process(
    const MotionPacket *raw_cmd, uint32_t packet_age_ms,
    const UltrasonicArrayReadings *us_data, const IRReadings *ir_data,
    uint32_t current_time_ms, SafeMotionOutput *out_motion)
{
    (void)us_data;
    (void)ir_data;
    (void)current_time_ms;

    if (!out_motion) return;
    memset(out_motion, 0, sizeof(SafeMotionOutput));

    if (packet_age_ms > 400 || raw_cmd == NULL) {
        out_motion->timeout_active = true;
        return;
    }

    if (raw_cmd->flags & MOTION_FLAG_ESTOP) {
        out_motion->estop_active = true;
        return;
    }

    MotionCommand in = { raw_cmd->linear, raw_cmd->angular };
    MotionCommand safe = applyCollisionFilter(in);

    out_motion->linear = safe.linear;
    out_motion->angular = safe.angular;
    out_motion->front_blocked = g_filter_state.front_ir_blocked || g_filter_state.front_us_stop || g_filter_state.front_us_slowdown || g_filter_state.front_us_all_stale;
    out_motion->side_left_blocked = g_filter_state.side_left_blocked;
    out_motion->side_right_blocked = g_filter_state.side_right_blocked;
    out_motion->rear_blocked = g_filter_state.rear_blocked;
}
