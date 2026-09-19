/**
 * @file motor_driver.h
 * @brief Differential drive motor controller interface for 4WD chassis driven by
 *        dual parallel-wired L298N drivers via ESP32.
 */

#ifndef MOTOR_DRIVER_H
#define MOTOR_DRIVER_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

// GPIO pin definitions for dual parallel-wired L298N drivers
#define MOTOR_LEFT_ENA_PIN    13
#define MOTOR_LEFT_IN1_PIN    12
#define MOTOR_LEFT_IN2_PIN    14

#define MOTOR_RIGHT_ENB_PIN   25
#define MOTOR_RIGHT_IN3_PIN   27
#define MOTOR_RIGHT_IN4_PIN   26

// LEDC PWM configuration
#define MOTOR_PWM_FREQ_HZ     1000
#define MOTOR_PWM_RES_BITS    8
#define MOTOR_LEFT_PWM_CH     0
#define MOTOR_RIGHT_PWM_CH    1

/**
 * @brief Initializes motor driver GPIO pins and LEDC PWM channels.
 */
void motorDriverInit(void);

/**
 * @brief Drives one side of the robot (left or right).
 *
 * Hard safety rule enforced: Opposite direction pin is always pulled LOW before
 * setting the active pin HIGH to guarantee both pins are never HIGH simultaneously.
 *
 * @param v Speed and direction (-100 to 100).
 * @param ena_pin Enable / PWM pin.
 * @param in1_pin Direction pin A.
 * @param in2_pin Direction pin B.
 * @param pwm_channel LEDC PWM channel associated with ena_pin.
 */
void driveSide(int8_t v, int ena_pin, int in1_pin, int in2_pin, int pwm_channel);

/**
 * @brief Sets differential drive velocities for both sides.
 *
 * Differential mixing:
 *   left  = clamp(linear + angular, -100, 100)
 *   right = clamp(linear - angular, -100, 100)
 *
 * @param linear Forward/backward speed percentage (-100 to 100).
 * @param angular Turn rate percentage (-100 to 100).
 */
void driveMotors(int8_t linear, int8_t angular);

// Backward-compatibility wrappers
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

void motor_driver_init(const MotorDriverPinConfig *config);
void motor_driver_set_speed(int8_t linear, int8_t angular);
void motor_driver_stop(void);

#ifdef __cplusplus
}
#endif

#endif // MOTOR_DRIVER_H
