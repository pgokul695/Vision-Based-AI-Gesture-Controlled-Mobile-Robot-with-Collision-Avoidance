/**
 * @file ultrasonic.cpp
 * @brief Stub implementation for 3-unit front ultrasonic sensor array with round-robin pinging.
 */

#include "sensors/ultrasonic.h"

// Internal module state
static UltrasonicArrayPinConfig g_pins;
static UltrasonicArrayReadings g_readings = {
    { -1.0f, 0, false }, // left
    { -1.0f, 0, false }, // center
    { -1.0f, 0, false }  // right
};
static UltrasonicSensorIndex g_active_sensor = US_SENSOR_LEFT;
static uint32_t g_last_ping_ms = 0;

void ultrasonic_init(const UltrasonicArrayPinConfig *config) {
    if (config) {
        g_pins = *config;
    }

    // TODO: Configure trig_pin as OUTPUT and echo_pin as INPUT for all 3 sensors
    // TODO: Ensure trigger pins are pulled LOW initially
}

void ultrasonic_update(void) {
    // TODO: Implement non-blocking round-robin trigger and echo pulse-width measurement:
    // 1. Wait at least 30ms between pings to avoid acoustic reflections and cross-talk.
    // 2. Pulse trig_pin for active sensor (10 microseconds HIGH).
    // 3. Measure pulse duration on echo_pin (or use interrupts/RMT peripheral).
    // 4. Calculate distance_cm = (duration_us / 2.0f) * 0.0343f.
    // 5. Store result in g_readings with timestamp.
    // 6. Switch g_active_sensor to (g_active_sensor + 1) % US_SENSOR_COUNT.
}

void ultrasonic_get_readings(UltrasonicArrayReadings *out_readings) {
    if (out_readings) {
        *out_readings = g_readings;
    }
}

uint32_t ultrasonic_get_reading_age_ms(UltrasonicSensorIndex sensor, uint32_t current_time_ms) {
    uint32_t ts = 0;
    switch (sensor) {
        case US_SENSOR_LEFT:
            ts = g_readings.left.timestamp_ms;
            break;
        case US_SENSOR_CENTER:
            ts = g_readings.center.timestamp_ms;
            break;
        case US_SENSOR_RIGHT:
            ts = g_readings.right.timestamp_ms;
            break;
        default:
            return UINT32_MAX;
    }

    if (current_time_ms >= ts) {
        return current_time_ms - ts;
    }
    return 0;
}
