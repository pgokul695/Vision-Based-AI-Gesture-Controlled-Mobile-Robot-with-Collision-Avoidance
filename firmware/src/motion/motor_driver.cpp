/**
 * @file motor_driver.cpp
 * @brief Differential drive motor controller implementation for dual parallel-wired L298N drivers.
 */

#include "motion/motor_driver.h"
#include <Arduino.h>

static inline int8_t clamp_val(int16_t val, int8_t min_v, int8_t max_v) {
    if (val < min_v) return min_v;
    if (val > max_v) return max_v;
    return (int8_t)val;
}

void driveSide(int8_t v, int ena_pin, int in1_pin, int in2_pin, int pwm_channel) {
    (void)ena_pin; // Pin is attached to pwm_channel during initialization
    uint32_t duty = 0;

    if (v > 0) {
        // Forward: IN_a = HIGH, IN_b = LOW
        // Hard safety rule, non-negotiable: write the pin turning OFF to LOW
        // BEFORE writing the pin turning ON to HIGH.
        digitalWrite(in2_pin, LOW);
        digitalWrite(in1_pin, HIGH);
        duty = ((uint32_t)v * 255) / 100;
    } else if (v < 0) {
        // Reverse: IN_a = LOW, IN_b = HIGH
        // Hard safety rule, non-negotiable: write the pin turning OFF to LOW
        // BEFORE writing the pin turning ON to HIGH.
        digitalWrite(in1_pin, LOW);
        digitalWrite(in2_pin, HIGH);
        duty = ((uint32_t)(-v) * 255) / 100;
    } else {
        // Coast / Stop: both LOW
        digitalWrite(in1_pin, LOW);
        digitalWrite(in2_pin, LOW);
        duty = 0;
    }

    ledcWrite(pwm_channel, duty);
}

void driveMotors(int8_t linear, int8_t angular) {
    // Mixing:
    // left = clamp(linear + angular, -100, 100)
    // right = clamp(linear - angular, -100, 100)
    int8_t left = clamp_val((int16_t)linear + (int16_t)angular, -100, 100);
    int8_t right = clamp_val((int16_t)linear - (int16_t)angular, -100, 100);

    driveSide(left, MOTOR_LEFT_ENA_PIN, MOTOR_LEFT_IN1_PIN, MOTOR_LEFT_IN2_PIN, MOTOR_LEFT_PWM_CH);
    driveSide(right, MOTOR_RIGHT_ENB_PIN, MOTOR_RIGHT_IN3_PIN, MOTOR_RIGHT_IN4_PIN, MOTOR_RIGHT_PWM_CH);
}

void motorDriverInit(void) {
    // 1. Configure direction pins as outputs and ensure initial LOW state
    pinMode(MOTOR_LEFT_IN1_PIN, OUTPUT);
    digitalWrite(MOTOR_LEFT_IN1_PIN, LOW);
    pinMode(MOTOR_LEFT_IN2_PIN, OUTPUT);
    digitalWrite(MOTOR_LEFT_IN2_PIN, LOW);

    pinMode(MOTOR_RIGHT_IN3_PIN, OUTPUT);
    digitalWrite(MOTOR_RIGHT_IN3_PIN, LOW);
    pinMode(MOTOR_RIGHT_IN4_PIN, OUTPUT);
    digitalWrite(MOTOR_RIGHT_IN4_PIN, LOW);

    // 2. Set up LEDC PWM channels and attach to enable pins
    ledcSetup(MOTOR_LEFT_PWM_CH, MOTOR_PWM_FREQ_HZ, MOTOR_PWM_RES_BITS);
    ledcAttachPin(MOTOR_LEFT_ENA_PIN, MOTOR_LEFT_PWM_CH);
    ledcWrite(MOTOR_LEFT_PWM_CH, 0);

    ledcSetup(MOTOR_RIGHT_PWM_CH, MOTOR_PWM_FREQ_HZ, MOTOR_PWM_RES_BITS);
    ledcAttachPin(MOTOR_RIGHT_ENB_PIN, MOTOR_RIGHT_PWM_CH);
    ledcWrite(MOTOR_RIGHT_PWM_CH, 0);

    // Zero initial state
    driveMotors(0, 0);
}

// Backward-compatibility wrappers
void motor_driver_init(const MotorDriverPinConfig *config) {
    (void)config;
    motorDriverInit();
}

void motor_driver_set_speed(int8_t linear, int8_t angular) {
    driveMotors(linear, angular);
}

void motor_driver_stop(void) {
    driveMotors(0, 0);
}
