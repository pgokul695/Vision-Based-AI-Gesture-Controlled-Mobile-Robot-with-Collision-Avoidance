/**
 * @file main.cpp
 * @brief Full ESP32 Mobile Robot Firmware
 *
 * Integrates:
 * 1. UDP packet receiver (port 5005) with 400ms failsafe timeout
 * 2. Non-blocking round-robin ultrasonic array (3 front sensors, interrupt pulse measurement)
 * 3. 5-point digital IR proximity sensor array (active-low, polled every loop)
 * 4. Multi-zone collision arbiter with proportional slowdown, reflex stop, and turn gating
 * 5. Dual parallel-wired L298N motor driver (LEDC PWM)
 * 6. Live SSD1306 OLED telemetry display (~5Hz)
 */

#include <Arduino.h>
#include <WiFi.h>
#include "motion_packet.h"
#include "network/wifi_credentials.h"
#include "network/udp_receiver.h"
#include "motion/motor_driver.h"
#include "motion/collision_filter.h"
#include "sensors/ultrasonic.h"
#include "sensors/ir.h"
#include "display/oled_debug.h"

#define ROBOT_UDP_PORT 5005

static uint32_t g_last_timeout_log_ms = 0;
static MotionPacket g_last_pkt;
static bool g_has_packet = false;
static UdpPacketStats g_last_stats = {0};

/**
 * @brief Connects to Wi-Fi with OLED and Serial status feedback.
 */
static void connect_wifi(void) {
    WiFi.mode(WIFI_STA);

    while (true) {
        Serial.printf("[WIFI] Connecting to SSID: \"%s\" ...\n", WIFI_SSID);
        WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

        uint32_t start_ms = millis();
        const uint32_t timeout_ms = 15000;

        while (WiFi.status() != WL_CONNECTED && (millis() - start_ms < timeout_ms)) {
            OledTelemetryData telem = {0};
            telem.wifi_connected = false;
            oled_debug_update(&telem, millis(), true);
            delay(100);
        }

        if (WiFi.status() == WL_CONNECTED) {
            Serial.println(F("[WIFI] Connected successfully!"));
            Serial.print(F("[WIFI] Assigned IP address: "));
            Serial.println(WiFi.localIP());
            Serial.printf("[WIFI] Signal strength (RSSI): %d dBm\n", WiFi.RSSI());
            break;
        }

        Serial.println(F("[WIFI ERROR] Connection timed out after 15s. Retrying in 2 seconds..."));
        WiFi.disconnect();
        delay(2000);
    }
}

void setup() {
    Serial.begin(115200);
    delay(500);

    Serial.println(F("\n=================================================="));
    Serial.println(F("  ESP32 Full Robot Firmware (Motors + Sensors + OLED)"));
    Serial.println(F("=================================================="));

    // 1. Initialize OLED Debug Display (I2C SDA=21, SCL=22)
    if (!oled_debug_init()) {
        Serial.println(F("[WARN] OLED initialization failed or display absent"));
    }

    // 2. Connect to Wi-Fi network
    connect_wifi();

    // 3. Initialize dual parallel-wired L298N motor drivers
    motorDriverInit();

    // 4. Initialize ultrasonic sensor array (D15/D2, D23/D35, D33/D32)
    ultrasonic_init(NULL);

    // 5. Initialize digital IR sensor array (D34, D5, D19, D4, D18)
    ir_init(NULL);

    // 6. Initialize collision arbiter
    collision_filter_init();

    // 7. Initialize UDP receiver on configured port
    UdpReceiverConfig udp_cfg = { ROBOT_UDP_PORT };
    if (!udp_receiver_init(&udp_cfg)) {
        Serial.println(F("[FATAL] Failed to initialize UDP receiver!"));
    }

    Serial.printf("[READY] Listening on %s:%u\n", WiFi.localIP().toString().c_str(), ROBOT_UDP_PORT);
    Serial.println(F("[READY] All sensor modules and collision arbiter online"));
    Serial.println(F("[READY] Drivetrain armed: Dual parallel-wired L298N active"));
    Serial.println(F("==================================================\n"));
}

void loop() {
    uint32_t now_ms = millis();

    // Check Wi-Fi connection health
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println(F("[WIFI WARN] Connection lost. Reconnecting..."));
        driveMotors(0, 0);
        connect_wifi();
        return;
    }

    // Step 1: Advance ultrasonic round-robin state machine
    ultrasonic_update();

    // Step 2: Read all 5 digital IR pins
    ir_update(now_ms);

    // Step 3: Check for incoming UDP packet & 400ms fail-safe timeout
    MotionPacket pkt;
    UdpPacketStats stats;
    bool received = udp_receiver_poll_stats(&pkt, &stats, now_ms);
    uint32_t age_ms = udp_receiver_get_time_since_last_packet_ms(now_ms);
    bool is_timeout = (age_ms > 400);

    if (received) {
        g_last_pkt = pkt;
        g_has_packet = true;
        g_last_stats = stats;

        // Sequence gap notification
        if (stats.has_gap) {
            Serial.printf("[WARN] Sequence gap detected: missed %u (expected %u, got %u)\n",
                          stats.missed_count, stats.expected_seq, stats.received_seq);
        }

        // Diagnostic line from connectivity test
        Serial.printf("[UDP] seq=%u  lin=%d  ang=%d  flags=0x%02X  age=%ums  rate=%.1fHz\n",
                      pkt.seq, pkt.linear, pkt.angular, pkt.flags, stats.age_ms, stats.rate_hz);
    }

    MotionCommand incomingCommand = {0, 0};
    if (!is_timeout && g_has_packet && !(g_last_pkt.flags & MOTION_FLAG_ESTOP)) {
        incomingCommand.linear = g_last_pkt.linear;
        incomingCommand.angular = g_last_pkt.angular;
    } else {
        incomingCommand.linear = 0;
        incomingCommand.angular = 0;
    }

    // Step 4: Apply multi-zone collision avoidance safety filter
    MotionCommand safeCommand = applyCollisionFilter(incomingCommand);

    // Step 5: Drive motors with safe filtered velocities
    driveMotors(safeCommand.linear, safeCommand.angular);

    if (safeCommand.linear != 0 || safeCommand.angular != 0) {
        int16_t left = (int16_t)safeCommand.linear + (int16_t)safeCommand.angular;
        int16_t right = (int16_t)safeCommand.linear - (int16_t)safeCommand.angular;
        if (left > 100) left = 100; else if (left < -100) left = -100;
        if (right > 100) right = 100; else if (right < -100) right = -100;
        Serial.printf("[MOTOR] Left: %d%% (PWM %u) | Right: %d%% (PWM %u)\n",
                      left, (abs(left) * 255) / 100,
                      right, (abs(right) * 255) / 100);
    }

    // Failsafe timeout diagnostic log (once per second)
    if (is_timeout) {
        if (now_ms - g_last_timeout_log_ms >= 1000) {
            if (age_ms == UINT32_MAX) {
                Serial.println(F("[FAILSAFE] No signal from controller: waiting for initial packets..."));
            } else {
                Serial.printf("[FAILSAFE] No signal from controller: packet age %ums > 400ms timeout\n", age_ms);
            }
            g_last_timeout_log_ms = now_ms;
        }
    }

    // Step 6: Update OLED debug display (~5Hz rate-limited)
    char ip_str[24];
    snprintf(ip_str, sizeof(ip_str), "%s", WiFi.localIP().toString().c_str());

    OledTelemetryData telem;
    telem.wifi_ip = ip_str;
    telem.wifi_connected = (WiFi.status() == WL_CONNECTED);
    telem.packet_rate_hz = g_last_stats.rate_hz;
    telem.signal_timeout = is_timeout;
    telem.in_linear = incomingCommand.linear;
    telem.in_angular = incomingCommand.angular;
    telem.out_linear = safeCommand.linear;
    telem.out_angular = safeCommand.angular;
    telem.us_left_cm = getDistanceCm(US_POS_FRONT_LEFT);
    telem.us_center_cm = getDistanceCm(US_POS_FRONT_CENTER);
    telem.us_right_cm = getDistanceCm(US_POS_FRONT_RIGHT);
    telem.us_left_stale = ultrasonic_is_stale(US_POS_FRONT_LEFT);
    telem.us_center_stale = ultrasonic_is_stale(US_POS_FRONT_CENTER);
    telem.us_right_stale = ultrasonic_is_stale(US_POS_FRONT_RIGHT);
    telem.ir_fl = isTriggered(IR_POS_FRONT_LEFT);
    telem.ir_fr = isTriggered(IR_POS_FRONT_RIGHT);
    telem.ir_sl = isTriggered(IR_POS_SIDE_LEFT);
    telem.ir_sr = isTriggered(IR_POS_SIDE_RIGHT);
    telem.ir_rc = isTriggered(IR_POS_REAR_CENTER);

    oled_debug_update(&telem, now_ms, false);

    // Yield control loop throttle
    delay(2);
}
