/**
 * @file ultrasonic.h
 * @brief Interface for 3-unit front ultrasonic sensor array with non-blocking round-robin triggering.
 *
 * Front array topology:
 * - Front-Left:   Trig D15, Echo D2
 * - Front-Center: Trig D23, Echo D35 (swapped with D34 for GPIO output capability)
 * - Front-Right:  Trig D33, Echo D32
 *
 * Sensors are pinged sequentially in round-robin fashion (never simultaneously)
 * with interrupt-driven pulse width capture and a bounded 25ms timeout.
 */

#ifndef ULTRASONIC_H
#define ULTRASONIC_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

// Default pin assignments matching confirmed hardware pinout (D34/D23 swap applied)
#define US_FRONT_LEFT_TRIG_PIN    15
#define US_FRONT_LEFT_ECHO_PIN    2
#define US_FRONT_CENTER_TRIG_PIN  23
#define US_FRONT_CENTER_ECHO_PIN  35
#define US_FRONT_RIGHT_TRIG_PIN   33
#define US_FRONT_RIGHT_ECHO_PIN   32

#define US_ECHO_TIMEOUT_MS        25
#define US_INTER_PING_DELAY_MS    10
#define US_STALE_TIMEOUT_MS       300

typedef enum {
    US_POS_FRONT_LEFT = 0,
    US_POS_FRONT_CENTER = 1,
    US_POS_FRONT_RIGHT = 2,
    // Aliases for compatibility
    US_SENSOR_LEFT = 0,
    US_SENSOR_CENTER = 1,
    US_SENSOR_RIGHT = 2,
    US_SENSOR_COUNT = 3
} UltrasonicPosition;

typedef UltrasonicPosition UltrasonicSensorIndex;

/**
 * @brief Reading for a single ultrasonic sensor.
 */
typedef struct {
    float distance_cm;      // Measured distance in centimeters (-1.0f if out-of-range or stale)
    uint32_t timestamp_ms;  // System millisecond timestamp when last valid reading was obtained
    bool valid;             // True if latest reading was successful
} UltrasonicSensorReading;

/**
 * @brief Aggregate readings for the 3 front ultrasonic sensors.
 */
typedef struct {
    UltrasonicSensorReading left;
    UltrasonicSensorReading center;
    UltrasonicSensorReading right;
} UltrasonicArrayReadings;

/**
 * @brief Pin configuration for an ultrasonic sensor unit.
 */
typedef struct {
    uint8_t trig_pin;
    uint8_t echo_pin;
} UltrasonicSensorPinConfig;

typedef struct {
    UltrasonicSensorPinConfig left;
    UltrasonicSensorPinConfig center;
    UltrasonicSensorPinConfig right;
} UltrasonicArrayPinConfig;

/**
 * @brief Initializes GPIO pins and external interrupts for the ultrasonic array.
 * @param config Optional custom pin allocation (NULL uses default hardware map).
 */
void ultrasonic_init(const UltrasonicArrayPinConfig *config);

/**
 * @brief Non-blocking state machine update. Call once per main loop iteration.
 */
void ultrasonic_update(void);

/**
 * @brief Returns distance in cm for specified sensor, or -1.0f if stale or invalid.
 */
float getDistanceCm(UltrasonicPosition pos);
float ultrasonic_get_distance_cm(UltrasonicPosition pos);

/**
 * @brief Returns age of the last valid reading in milliseconds.
 */
uint32_t getReadingAgeMs(UltrasonicPosition pos);
uint32_t ultrasonic_get_reading_age_ms(UltrasonicSensorIndex sensor, uint32_t current_time_ms);

/**
 * @brief Helper to check if a sensor's reading is considered stale (>300ms).
 */
bool ultrasonic_is_stale(UltrasonicPosition pos);

/**
 * @brief Retrieves all 3 sensor readings struct.
 */
void ultrasonic_get_readings(UltrasonicArrayReadings *out_readings);

#ifdef __cplusplus
}
#endif

#endif // ULTRASONIC_H
