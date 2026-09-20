/**
 * @file ir.cpp
 * @brief Implementation for 5 digital IR proximity sensors.
 */

#include "sensors/ir.h"
#include <Arduino.h>

static IRPinConfig g_ir_pins = {
    IR_FRONT_LEFT_PIN,
    IR_FRONT_RIGHT_PIN,
    IR_SIDE_LEFT_PIN,
    IR_SIDE_RIGHT_PIN,
    IR_REAR_CENTER_PIN,
    true // Active-low: LOW = obstacle detected
};

static IRReadings g_ir_readings = {false, false, false, false, false, 0};

void ir_init(const IRPinConfig *config) {
    if (config) {
        g_ir_pins = *config;
    }

    // Pin 34 is input-only without internal pullup resistor
    if (g_ir_pins.front_left_pin >= 34) {
        pinMode(g_ir_pins.front_left_pin, INPUT);
    } else {
        pinMode(g_ir_pins.front_left_pin, INPUT_PULLUP);
    }

    pinMode(g_ir_pins.front_right_pin, INPUT_PULLUP);
    pinMode(g_ir_pins.side_left_pin, INPUT_PULLUP);
    pinMode(g_ir_pins.side_right_pin, INPUT_PULLUP);
    pinMode(g_ir_pins.rear_center_pin, INPUT_PULLUP);
}

void ir_update(uint32_t current_time_ms) {
    g_ir_readings.sample_timestamp_ms = current_time_ms;

    int fl_raw = digitalRead(g_ir_pins.front_left_pin);
    int fr_raw = digitalRead(g_ir_pins.front_right_pin);
    int sl_raw = digitalRead(g_ir_pins.side_left_pin);
    int sr_raw = digitalRead(g_ir_pins.side_right_pin);
    int rc_raw = digitalRead(g_ir_pins.rear_center_pin);

    if (g_ir_pins.active_low) {
        g_ir_readings.front_left_triggered   = (fl_raw == LOW);
        g_ir_readings.front_right_triggered  = (fr_raw == LOW);
        g_ir_readings.side_left_triggered    = (sl_raw == LOW);
        g_ir_readings.side_right_triggered   = (sr_raw == LOW);
        g_ir_readings.rear_center_triggered  = (rc_raw == LOW);
    } else {
        g_ir_readings.front_left_triggered   = (fl_raw == HIGH);
        g_ir_readings.front_right_triggered  = (fr_raw == HIGH);
        g_ir_readings.side_left_triggered    = (sl_raw == HIGH);
        g_ir_readings.side_right_triggered   = (sr_raw == HIGH);
        g_ir_readings.rear_center_triggered  = (rc_raw == HIGH);
    }
}

bool isTriggered(IRPosition pos) {
    switch (pos) {
        case IR_POS_FRONT_LEFT:   return g_ir_readings.front_left_triggered;
        case IR_POS_FRONT_RIGHT:  return g_ir_readings.front_right_triggered;
        case IR_POS_SIDE_LEFT:    return g_ir_readings.side_left_triggered;
        case IR_POS_SIDE_RIGHT:   return g_ir_readings.side_right_triggered;
        case IR_POS_REAR_CENTER:  return g_ir_readings.rear_center_triggered;
        default: return false;
    }
}

bool ir_is_triggered(IRPosition pos) {
    return isTriggered(pos);
}

void ir_get_readings(IRReadings *out_readings) {
    if (out_readings) {
        *out_readings = g_ir_readings;
    }
}
