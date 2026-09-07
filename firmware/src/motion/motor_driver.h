/**
 * @file motor_driver.h
 * @brief Differential drive motor controller interface for DC motors via H-Bridge (L298N / DRV8833).
 */

#ifndef MOTOR_DRIVER_H
#define MOTOR_DRIVER_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    uint8_t left_in1_pin;
    uint8_t left_in2_pin;
    uint8_t left_enable_pwm_pin;
    uint8_t right_in1_pin;
    uint8_t right_in2_pin;
    uint8_t right_enable_pwm_pin;
    uint32_t pwm_frequency_hz;
    uint8_t pwm_resolution_bits;
} MotorDriverPinConfig;

/**
 * @brief Initializes motor driver GPIO pins and PWM channels.
 * @param config Pin mapping and PWM setup.
 */
void motor_driver_init(const MotorDriverPinConfig *config);

/**
 * @brief Sets differential drive velocities from normalized linear and angular percentages.
 *
 * Differential mixing formula:
 *   left_speed  = linear - angular
 *   right_speed = linear + angular
 *
 * @param linear Forward/backward speed percentage (-100 to 100).
 * @param angular Turn rate percentage (-100 to 100).
 */
void motor_driver_set_speed(int8_t linear, int8_t angular);

/**
 * @brief Immediately stops both motors and disables PWM outputs.
 */
void motor_driver_stop(void);

#ifdef __cplusplus
}
#endif

#endif // MOTOR_DRIVER_H
