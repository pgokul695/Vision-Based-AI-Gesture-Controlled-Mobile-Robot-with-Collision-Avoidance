/**
 * @file ir.h
 * @brief Interface for 5 digital IR proximity sensors.
 *
 * Sensor topology (swapped D34 and D23 for hardware compatibility):
 * - Front-Left:   D34 (GPI input-only pin)
 * - Front-Right:  D5
 * - Side-Left:    D19
 * - Side-Right:   D4
 * - Rear-Center:  D18
 *
 * Polled directly via GPIO digital read on every control loop iteration.
 */

#ifndef IR_H
#define IR_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

// Pin assignments matching hardware pin map
#define IR_FRONT_LEFT_PIN    34
#define IR_FRONT_RIGHT_PIN   5
#define IR_SIDE_LEFT_PIN     19
#define IR_SIDE_RIGHT_PIN    4
#define IR_REAR_CENTER_PIN   18

typedef enum {
    IR_POS_FRONT_LEFT = 0,
    IR_POS_FRONT_RIGHT = 1,
    IR_POS_SIDE_LEFT = 2,
    IR_POS_SIDE_RIGHT = 3,
    IR_POS_REAR_CENTER = 4,
    // Aliases
    IR_SENSOR_FRONT_LEFT = 0,
    IR_SENSOR_FRONT_RIGHT = 1,
    IR_SENSOR_SIDE_LEFT = 2,
    IR_SENSOR_SIDE_RIGHT = 3,
    IR_SENSOR_REAR_CENTER = 4,
    IR_SENSOR_COUNT = 5
} IRSensorIndex;

typedef IRSensorIndex IRPosition;

/**
 * @brief Status of all 5 digital IR sensors.
 * Note: A value of true indicates an obstacle is detected within threshold.
 */
typedef struct {
    bool front_left_triggered;
    bool front_right_triggered;
    bool side_left_triggered;
    bool side_right_triggered;
    bool rear_center_triggered;
    uint32_t sample_timestamp_ms;
} IRReadings;

/**
 * @brief GPIO pin mapping for the 5 IR sensors.
 */
typedef struct {
    uint8_t front_left_pin;
    uint8_t front_right_pin;
    uint8_t side_left_pin;
    uint8_t side_right_pin;
    uint8_t rear_center_pin;
    bool active_low; // Most digital IR modules output LOW when obstacle is detected
} IRPinConfig;

/**
 * @brief Initializes digital input pins for all 5 IR sensors.
 * @param config Optional custom pin allocation (NULL uses default hardware map).
 */
void ir_init(const IRPinConfig *config);

/**
 * @brief Polls all 5 IR sensor pins and updates internal state.
 * Called on every main loop cycle.
 */
void ir_update(uint32_t current_time_ms);

/**
 * @brief Returns true if specified IR sensor detects an obstacle.
 */
bool isTriggered(IRPosition pos);
bool ir_is_triggered(IRPosition pos);

/**
 * @brief Retrieves the latest polled IR readings.
 * @param out_readings Output struct populated with detection booleans.
 */
void ir_get_readings(IRReadings *out_readings);

/**
 * @brief Helper to check if any front IR sensor is tripped.
 */
static inline bool ir_is_front_blocked(const IRReadings *readings) {
    if (!readings) return false;
    return readings->front_left_triggered || readings->front_right_triggered;
}

#ifdef __cplusplus
}
#endif

#endif // IR_H
