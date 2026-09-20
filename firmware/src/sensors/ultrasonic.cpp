/**
 * @file ultrasonic.cpp
 * @brief Non-blocking round-robin ultrasonic driver with interrupt pulse measurement.
 */

#include "sensors/ultrasonic.h"
#include <Arduino.h>

enum PingState {
    PING_STATE_TRIGGER,
    PING_STATE_WAIT_ECHO,
    PING_STATE_INTER_PING_DELAY
};

static UltrasonicArrayPinConfig g_pins = {
    { US_FRONT_LEFT_TRIG_PIN, US_FRONT_LEFT_ECHO_PIN },
    { US_FRONT_CENTER_TRIG_PIN, US_FRONT_CENTER_ECHO_PIN },
    { US_FRONT_RIGHT_TRIG_PIN, US_FRONT_RIGHT_ECHO_PIN }
};

static UltrasonicArrayReadings g_readings = {
    { -1.0f, 0, false }, // left
    { -1.0f, 0, false }, // center
    { -1.0f, 0, false }  // right
};

// Interrupt-driven timing state
static volatile uint32_t g_echo_start_us[US_SENSOR_COUNT] = {0, 0, 0};
static volatile uint32_t g_echo_end_us[US_SENSOR_COUNT] = {0, 0, 0};
static volatile bool g_echo_done[US_SENSOR_COUNT] = {false, false, false};

static UltrasonicPosition g_active_sensor = US_POS_FRONT_LEFT;
static PingState g_state = PING_STATE_TRIGGER;
static uint32_t g_step_time_ms = 0;

static void IRAM_ATTR echo_isr_left(void) {
    if (digitalRead(g_pins.left.echo_pin) == HIGH) {
        g_echo_start_us[US_POS_FRONT_LEFT] = micros();
    } else {
        g_echo_end_us[US_POS_FRONT_LEFT] = micros();
        g_echo_done[US_POS_FRONT_LEFT] = true;
    }
}

static void IRAM_ATTR echo_isr_center(void) {
    if (digitalRead(g_pins.center.echo_pin) == HIGH) {
        g_echo_start_us[US_POS_FRONT_CENTER] = micros();
    } else {
        g_echo_end_us[US_POS_FRONT_CENTER] = micros();
        g_echo_done[US_POS_FRONT_CENTER] = true;
    }
}

static void IRAM_ATTR echo_isr_right(void) {
    if (digitalRead(g_pins.right.echo_pin) == HIGH) {
        g_echo_start_us[US_POS_FRONT_RIGHT] = micros();
    } else {
        g_echo_end_us[US_POS_FRONT_RIGHT] = micros();
        g_echo_done[US_POS_FRONT_RIGHT] = true;
    }
}

static inline uint8_t get_active_trig_pin(UltrasonicPosition pos) {
    switch (pos) {
        case US_POS_FRONT_LEFT:   return g_pins.left.trig_pin;
        case US_POS_FRONT_CENTER: return g_pins.center.trig_pin;
        case US_POS_FRONT_RIGHT:  return g_pins.right.trig_pin;
        default: return 0;
    }
}

static UltrasonicSensorReading* get_sensor_reading_ptr(UltrasonicPosition pos) {
    switch (pos) {
        case US_POS_FRONT_LEFT:   return &g_readings.left;
        case US_POS_FRONT_CENTER: return &g_readings.center;
        case US_POS_FRONT_RIGHT:  return &g_readings.right;
        default: return nullptr;
    }
}

void ultrasonic_init(const UltrasonicArrayPinConfig *config) {
    if (config) {
        g_pins = *config;
    }

    // Configure trigger pins as outputs and pull LOW
    pinMode(g_pins.left.trig_pin, OUTPUT);
    digitalWrite(g_pins.left.trig_pin, LOW);

    pinMode(g_pins.center.trig_pin, OUTPUT);
    digitalWrite(g_pins.center.trig_pin, LOW);

    pinMode(g_pins.right.trig_pin, OUTPUT);
    digitalWrite(g_pins.right.trig_pin, LOW);

    // Configure echo pins as inputs (D35 is input-only; others general input)
    pinMode(g_pins.left.echo_pin, INPUT);
    pinMode(g_pins.center.echo_pin, INPUT);
    pinMode(g_pins.right.echo_pin, INPUT);

    // Attach pin change interrupts
    attachInterrupt(digitalPinToInterrupt(g_pins.left.echo_pin), echo_isr_left, CHANGE);
    attachInterrupt(digitalPinToInterrupt(g_pins.center.echo_pin), echo_isr_center, CHANGE);
    attachInterrupt(digitalPinToInterrupt(g_pins.right.echo_pin), echo_isr_right, CHANGE);

    g_state = PING_STATE_TRIGGER;
    g_active_sensor = US_POS_FRONT_LEFT;
    g_step_time_ms = millis();
}

void ultrasonic_update(void) {
    uint32_t now_ms = millis();

    switch (g_state) {
        case PING_STATE_TRIGGER: {
            uint8_t trig_pin = get_active_trig_pin(g_active_sensor);
            int idx = (int)g_active_sensor;

            // Reset interrupt state for active sensor
            g_echo_done[idx] = false;
            g_echo_start_us[idx] = 0;
            g_echo_end_us[idx] = 0;

            // Fire 10 microsecond trigger pulse
            digitalWrite(trig_pin, HIGH);
            delayMicroseconds(10);
            digitalWrite(trig_pin, LOW);

            g_step_time_ms = now_ms;
            g_state = PING_STATE_WAIT_ECHO;
            break;
        }

        case PING_STATE_WAIT_ECHO: {
            int idx = (int)g_active_sensor;
            UltrasonicSensorReading *r = get_sensor_reading_ptr(g_active_sensor);

            if (g_echo_done[idx]) {
                // Echo pulse successfully captured
                uint32_t start_us = g_echo_start_us[idx];
                uint32_t end_us = g_echo_end_us[idx];

                if (end_us > start_us) {
                    uint32_t duration_us = end_us - start_us;
                    // Speed of sound = 343 m/s = 0.0343 cm/us -> dist = (duration * 0.0343) / 2
                    float dist = (duration_us * 0.0343f) / 2.0f;

                    if (dist >= 2.0f && dist <= 400.0f) {
                        r->distance_cm = dist;
                        r->timestamp_ms = now_ms;
                        r->valid = true;
                    } else {
                        r->valid = false;
                        // Note: timestamp_ms is preserved so stale check can detect prolonged invalidity
                    }
                } else {
                    r->valid = false;
                }

                g_step_time_ms = now_ms;
                g_state = PING_STATE_INTER_PING_DELAY;
            } else if (now_ms - g_step_time_ms >= US_ECHO_TIMEOUT_MS) {
                // Bounded timeout (25ms exceeded without echo completion)
                if (r) {
                    r->valid = false;
                    // Do NOT update timestamp_ms on timeout: reading age must continue growing
                }
                g_step_time_ms = now_ms;
                g_state = PING_STATE_INTER_PING_DELAY;
            }
            break;
        }

        case PING_STATE_INTER_PING_DELAY: {
            // Short 10ms acoustic attenuation delay before pinging adjacent transducer
            if (now_ms - g_step_time_ms >= US_INTER_PING_DELAY_MS) {
                g_active_sensor = (UltrasonicPosition)((g_active_sensor + 1) % US_SENSOR_COUNT);
                g_state = PING_STATE_TRIGGER;
            }
            break;
        }
    }
}

float getDistanceCm(UltrasonicPosition pos) {
    UltrasonicSensorReading *r = get_sensor_reading_ptr(pos);
    if (!r || !r->valid || ultrasonic_is_stale(pos)) {
        return -1.0f;
    }
    return r->distance_cm;
}

float ultrasonic_get_distance_cm(UltrasonicPosition pos) {
    return getDistanceCm(pos);
}

uint32_t getReadingAgeMs(UltrasonicPosition pos) {
    return ultrasonic_get_reading_age_ms(pos, millis());
}

uint32_t ultrasonic_get_reading_age_ms(UltrasonicSensorIndex sensor, uint32_t current_time_ms) {
    UltrasonicSensorReading *r = get_sensor_reading_ptr(sensor);
    if (!r || r->timestamp_ms == 0) {
        return UINT32_MAX;
    }
    if (current_time_ms >= r->timestamp_ms) {
        return current_time_ms - r->timestamp_ms;
    }
    return 0;
}

bool ultrasonic_is_stale(UltrasonicPosition pos) {
    return getReadingAgeMs(pos) > US_STALE_TIMEOUT_MS;
}

void ultrasonic_get_readings(UltrasonicArrayReadings *out_readings) {
    if (out_readings) {
        *out_readings = g_readings;
    }
}
