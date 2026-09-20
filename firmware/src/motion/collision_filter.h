/**
 * @file collision_filter.h
 * @brief Safety arbiter filtering incoming motion commands against obstacle sensors.
 */

#ifndef COLLISION_FILTER_H
#define COLLISION_FILTER_H

#include <stdint.h>
#include <stdbool.h>
#include "motion_packet.h"
#include "sensors/ir.h"
#include "sensors/ultrasonic.h"

#ifdef __cplusplus
extern "C" {
#endif

#define US_SLOWDOWN_DIST_CM  40.0f
#define US_STOP_DIST_CM      10.0f
#define US_READING_MAX_AGE_MS 300

typedef struct {
    int8_t linear;   // -100 to 100
    int8_t angular;  // -100 to 100
} MotionCommand;

typedef struct {
    MotionCommand cmd;
    bool front_us_slowdown;
    bool front_us_stop;
    bool front_us_all_stale;
    bool front_ir_blocked;
    bool side_left_blocked;
    bool side_right_blocked;
    bool rear_blocked;
    float min_front_dist_cm;
} CollisionFilterState;

/**
 * @brief Legacy safe motion structure for backward compatibility.
 */
typedef struct {
    int8_t linear;
    int8_t angular;
    bool estop_active;
    bool timeout_active;
    bool front_blocked;
    bool side_left_blocked;
    bool side_right_blocked;
    bool rear_blocked;
} SafeMotionOutput;

/**
 * @brief Initializes collision filter parameters.
 */
void collision_filter_init(void);

/**
 * @brief Filters incoming motion command against all sensor zones.
 * @param incoming Raw motion command requested by host.
 * @return Safe motion command to be dispatched to motors.
 */
MotionCommand applyCollisionFilter(MotionCommand incoming);

/**
 * @brief Retrieves the latest diagnostic state of the collision filter.
 */
void collision_filter_get_state(CollisionFilterState *out_state);

/**
 * @brief Legacy interface for packet-level processing.
 */
void collision_filter_process(
    const MotionPacket *raw_cmd, uint32_t packet_age_ms,
    const UltrasonicArrayReadings *us_data, const IRReadings *ir_data,
    uint32_t current_time_ms, SafeMotionOutput *out_motion);

#ifdef __cplusplus
}
#endif

#endif // COLLISION_FILTER_H
