/**
 * @file ultrasonic.h
 * @brief Interface for 3-unit front ultrasonic sensor array with round-robin triggering.
 *
 * Front array topology:
 * - Front-Left (~45° angled)
 * - Front-Center (0° forward)
 * - Front-Right (~45° angled)
 *
 * Sensors are pinged in round-robin fashion (never concurrently) to prevent
 * acoustic crosstalk between adjacent transducers.
 */

#ifndef ULTRASONIC_H
#define ULTRASONIC_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    US_SENSOR_LEFT = 0,
    US_SENSOR_CENTER = 1,
    US_SENSOR_RIGHT = 2,
    US_SENSOR_COUNT = 3
} UltrasonicSensorIndex;

/**
 * @brief Reading for a single ultrasonic sensor.
 */
typedef struct {
    float distance_cm;      // Measured distance in centimeters (-1.0f if out-of-range or error)
    uint32_t timestamp_ms;  // System millisecond timestamp when reading was obtained
    bool valid;             // True if reading is valid and within measurable range
} UltrasonicSensorReading;

/**
 * @brief Aggregate readings and ages for the 3 front ultrasonic sensors.
 */
typedef struct {
    UltrasonicSensorReading left;
    UltrasonicSensorReading center;
    UltrasonicSensorReading right;
} UltrasonicArrayReadings;

/**
 * @brief Pin configuration for an ultrasonic sensor unit (HC-SR04 / RCWL-1601).
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
 * @brief Initializes GPIO pins and timer state for the ultrasonic array.
 * @param config Pin allocations for left, center, and right sensors.
 */
void ultrasonic_init(const UltrasonicArrayPinConfig *config);

/**
 * @brief Advances the round-robin state machine.
 * Must be called periodically from the main loop. Pings only ONE sensor at a time
 * and yields between pings to ensure echo attenuation.
 */
void ultrasonic_update(void);

/**
 * @brief Retrieves the latest readings from all three front sensors.
 * @param out_readings Output struct containing distances and timestamps.
 */
void ultrasonic_get_readings(UltrasonicArrayReadings *out_readings);

/**
 * @brief Calculates the age of a sensor reading in milliseconds.
 *
 * @param sensor Index of sensor (left, center, right).
 * @param current_time_ms Current system timestamp in milliseconds.
 * @return Age of reading in milliseconds.
 */
uint32_t ultrasonic_get_reading_age_ms(UltrasonicSensorIndex sensor, uint32_t current_time_ms);

#ifdef __cplusplus
}
#endif

#endif // ULTRASONIC_H
