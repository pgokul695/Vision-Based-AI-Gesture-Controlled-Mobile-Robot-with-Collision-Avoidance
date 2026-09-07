/**
 * @file main.cpp
 * @brief ESP32 firmware entry point for Vision-Based AI Gesture-Controlled Mobile Robot.
 *
 * Execution flow:
 * 1. setup(): Initializes serial monitor, GPIOs, Wi-Fi AP/STA, UDP socket,
 *    sensors, and motor PWM peripherals.
 * 2. loop():
 *    a. Polls non-blocking UDP receiver for latest MotionPacket.
 *    b. Advances round-robin ultrasonic array and samples 5x IR sensors.
 *    c. Applies onboard collision avoidance arbitration (collision_filter).
 *    d. Dispatches safe velocities to differential motor driver.
 */

#include <Arduino.h>
#include "motion_packet.h"
#include "network/udp_receiver.h"
#include "sensors/ultrasonic.h"
#include "sensors/ir.h"
#include "motion/collision_filter.h"
#include "motion/motor_driver.h"

// Default UDP port
#define ROBOT_UDP_PORT 8888

static MotionPacket g_current_packet = {
    MOTION_PACKET_MAGIC,
    MOTION_PACKET_VERSION,
    0, 0, 0, 0,
    {0, 0, 0}
};

void setup() {
    Serial.begin(115200);
    Serial.println(F("[ROBOT] Booting Gesture-Controlled Mobile Robot firmware..."));

    // TODO: Connect to Wi-Fi network (or spin up SoftAP mode)
    // WiFi.mode(WIFI_STA);
    // WiFi.begin(WIFI_SSID, WIFI_PASS);

    // Initialize UDP receiver
    UdpReceiverConfig udp_cfg = { ROBOT_UDP_PORT };
    udp_receiver_init(&udp_cfg);

    // TODO: Define and initialize ultrasonic pin config
    // UltrasonicArrayPinConfig us_cfg = { ... };
    // ultrasonic_init(&us_cfg);

    // TODO: Define and initialize IR sensor pin config
    // IRPinConfig ir_cfg = { ... };
    // ir_init(&ir_cfg);

    // Initialize collision filter with default thresholds
    collision_filter_init(NULL);

    // TODO: Define and initialize motor driver pin config
    // MotorDriverPinConfig motor_cfg = { ... };
    // motor_driver_init(&motor_cfg);

    Serial.println(F("[ROBOT] Initialization complete. Entering control loop."));
}

void loop() {
    uint32_t now_ms = millis();

    // 1. Poll network for new motion command
    MotionPacket incoming_pkt;
    if (udp_receiver_poll(&incoming_pkt, now_ms)) {
        g_current_packet = incoming_pkt;
    }

    uint32_t packet_age_ms = udp_receiver_get_time_since_last_packet_ms(now_ms);

    // 2. Update sensor state
    ultrasonic_update();
    ir_update(now_ms);

    UltrasonicArrayReadings us_readings;
    ultrasonic_get_readings(&us_readings);

    IRReadings ir_readings;
    ir_get_readings(&ir_readings);

    // 3. Arbitrate safety via local collision filter
    SafeMotionOutput safe_cmd;
    collision_filter_process(
        &g_current_packet,
        packet_age_ms,
        &us_readings,
        &ir_readings,
        now_ms,
        &safe_cmd
    );

    // 4. Update motor driver outputs
    motor_driver_set_speed(safe_cmd.linear, safe_cmd.angular);

    // TODO: Optional telemetry transmission back to laptop
    delay(5); // Control loop throttle (~200Hz)
}
