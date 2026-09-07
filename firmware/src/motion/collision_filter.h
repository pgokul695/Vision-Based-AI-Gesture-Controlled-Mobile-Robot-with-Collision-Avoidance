/**
 * @file collision_filter.h
 * @brief Safety arbiter filtering incoming motion commands against obstacle sensors.
 *
 * Safety rules enforced:
 * 1. Failsafe Timeout: If elapsed time since last valid packet > 400ms -> output (0, 0).
 * 2. E-Stop: If packet has FLAG_ESTOP bit set -> output (0, 0).
 * 3. Front Zone (US + IR):
 *    - Hard stop on front IR trigger (linear <= 0 allowed, but positive forward linear is zeroed).
 *    - Proportional forward speed slowdown as ultrasonic distance decreases below threshold.
 * 4. Side Zones (Mid-IR):
 *    - Binary gate: If left side IR triggered, prohibit left turn (angular < 0 zeroed).
 *    - Binary gate: If right side IR triggered, prohibit right turn (angular > 0 zeroed).
 * 5. Rear Zone (Rear-IR):
 *    - Binary gate: If rear IR triggered, prohibit reverse (linear < 0 zeroed).
 */

#ifndef COLLISION_FILTER_H
#define COLLISION_FILTER_H

#include <stdint.h>
#include <stdbool.h>
#include "motion_packet.h"
#include "sensors/ultrasonic.h"
#include "sensors/ir.h"

#ifdef __cplusplus
extern "C" {
#endif

#define PACKET_TIMEOUT_MS          400
#define US_SLOWDOWN_DIST_CM        40.0f
#define US_STOP_DIST_CM            15.0f
#define US_READING_MAX_AGE_MS      300

/**
 * @brief Filtered and validated motion output safe to pass to motor drivers.
 */
typedef struct {
    int8_t linear;              // Safe linear speed (-100..100)
    int8_t angular;             // Safe angular turn rate (-100..100)
    bool estop_active;          // True if stopped due to host E-Stop flag
    bool timeout_active;        // True if stopped due to >400ms packet gap
    bool front_blocked;         // True if forward motion suppressed by front US or IR
    bool side_left_blocked;     // True if left turn suppressed by left IR
    bool side_right_blocked;    // True if right turn suppressed by right IR
    bool rear_blocked;          // True if reversing suppressed by rear IR
} SafeMotionOutput;

/**
 * @brief Threshold parameters for collision avoidance tuning.
 */
typedef struct {
    float us_slowdown_distance_cm;  // Distance at which linear speed scaling begins
    float us_stop_distance_cm;      // Distance at which forward motion is completely halted
    uint32_t packet_timeout_ms;     // Max allowable silence before failsafe stop (default 400ms)
    uint32_t max_sensor_age_ms;     // Max allowable sensor reading age before considered invalid
} CollisionFilterConfig;

/**
 * @brief Initializes collision filter configuration with default safe values.
 * @param config Optional custom configuration (NULL for defaults).
 */
void collision_filter_init(const CollisionFilterConfig *config);

/**
 * @brief Filters raw commanded motion packet through onboard safety arbitration.
 *
 * @param raw_cmd The received MotionPacket from host.
 * @param packet_age_ms Time in ms since raw_cmd was received.
 * @param us_data Current ultrasonic sensor array readings.
 * @param ir_data Current IR sensor readings.
 * @param current_time_ms System timestamp in ms.
 * @param out_motion Output structure containing safe velocities and intervention flags.
 */
void collision_filter_process(
    const MotionPacket *raw_cmd,
    uint32_t packet_age_ms,
    const UltrasonicArrayReadings *us_data,
    const IRReadings *ir_data,
    uint32_t current_time_ms,
    SafeMotionOutput *out_motion
);

#ifdef __cplusplus
}
#endif

#endif // COLLISION_FILTER_H
