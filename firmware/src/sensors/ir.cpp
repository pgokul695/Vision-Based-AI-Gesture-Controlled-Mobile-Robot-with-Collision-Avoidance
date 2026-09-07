/**
 * @file ir.cpp
 * @brief Stub implementation for 5 digital IR proximity sensors.
 */

#include "sensors/ir.h"

// Internal module state
static IRPinConfig g_ir_pins = {0, 0, 0, 0, 0, true};
static IRReadings g_ir_readings = {false, false, false, false, false, 0};

void ir_init(const IRPinConfig *config) {
    if (config) {
        g_ir_pins = *config;
    }

    // TODO: Configure all 5 IR GPIO pins as INPUT or INPUT_PULLUP
}

void ir_update(uint32_t current_time_ms) {
    g_ir_readings.sample_timestamp_ms = current_time_ms;

    // TODO: Read each GPIO pin (e.g. digitalRead(pin))
    // Determine triggered status based on g_ir_pins.active_low:
    // triggered = (raw_value == LOW) if active_low else (raw_value == HIGH)
    //
    // g_ir_readings.front_left_triggered   = ...;
    // g_ir_readings.front_right_triggered  = ...;
    // g_ir_readings.side_left_triggered    = ...;
    // g_ir_readings.side_right_triggered   = ...;
    // g_ir_readings.rear_center_triggered  = ...;
}

void ir_get_readings(IRReadings *out_readings) {
    if (out_readings) {
        *out_readings = g_ir_readings;
    }
}
