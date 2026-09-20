/**
 * @file main.cpp
 * @brief Full ESP32 Mobile Robot Firmware with Dual Transports & Fun Trick Sequencer
 *
 * Integrates:
 * 1. UDP packet receiver (port 5005)
 * 2. Async WebSocket receiver (port 80, /ws)
 * 3. Most-recent-packet arbitration across transports with unified 400ms fail-safe timeout
 * 4. Fun trick sequencer (1.5s canned spin on rising edge of FLAG_FUN_TRICK)
 * 5. Multi-zone collision arbiter with proportional slowdown, reflex stop, and turn gating
 * 6. Dual parallel-wired L298N motor driver (LEDC PWM)
 * 7. Live SSD1306 OLED telemetry display (~5Hz)
 */

#include <Arduino.h>
#include <WiFi.h>
#include "motion_packet.h"
#include "network/wifi_credentials.h"
#include "network/udp_receiver.h"
#include "network/ws_receiver.h"
#include "motion/motor_driver.h"
#include "motion/collision_filter.h"
#include "motion/trick_sequencer.h"
#include "motion/speed_mode.h"
#include "sensors/ultrasonic.h"
#include "sensors/ir.h"
#include "display/oled_debug.h"

#define ROBOT_UDP_PORT 5005
#define ROBOT_WS_PORT  80
#define ROBOT_WS_PATH  "/ws"

enum ActiveTransport {
    TRANSPORT_NONE = 0,
    TRANSPORT_UDP,
    TRANSPORT_WS
};

static uint32_t g_last_timeout_log_ms = 0;
static MotionPacket g_latest_pkt;
static bool g_has_packet = false;
static uint32_t g_latest_pkt_time_ms = 0;
static ActiveTransport g_latest_transport = TRANSPORT_NONE;
static float g_active_packet_rate_hz = 0.0f;
static bool g_prev_trick_flag = false;

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
    Serial.println(F("  ESP32 Full Robot Firmware (UDP + WebSocket + Trick)"));
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

    // 6. Initialize collision arbiter and trick sequencer
    collision_filter_init();
    trick_sequencer_init();

    // 7. Initialize UDP receiver on configured port
    UdpReceiverConfig udp_cfg = { ROBOT_UDP_PORT };
    if (!udp_receiver_init(&udp_cfg)) {
        Serial.println(F("[FATAL] Failed to initialize UDP receiver!"));
    }

    // 8. Initialize Async WebSocket receiver
    WsReceiverConfig ws_cfg = { ROBOT_WS_PORT, ROBOT_WS_PATH };
    if (!ws_receiver_init(&ws_cfg)) {
        Serial.println(F("[FATAL] Failed to initialize WebSocket receiver!"));
    }

    Serial.printf("[READY] UDP listening on %s:%u\n", WiFi.localIP().toString().c_str(), ROBOT_UDP_PORT);
    Serial.printf("[READY] WebSocket listening on ws://%s:%u%s\n", WiFi.localIP().toString().c_str(), ROBOT_WS_PORT, ROBOT_WS_PATH);
    Serial.println(F("[READY] All sensor modules, dual transports, and collision arbiter online"));
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

    // Step 1: Advance ultrasonic round-robin state machine & read IR pins
    ultrasonic_update();
    ir_update(now_ms);

    // Step 2: Poll both UDP and WebSocket transports
    MotionPacket udp_pkt;
    UdpPacketStats udp_stats;
    bool udp_received = udp_receiver_poll_stats(&udp_pkt, &udp_stats, now_ms);

    MotionPacket ws_pkt;
    WsPacketStats ws_stats;
    bool ws_received = ws_receiver_poll_stats(&ws_pkt, &ws_stats, now_ms);

    // Process UDP packet arrival
    if (udp_received) {
        if (udp_stats.has_gap) {
            Serial.printf("[UDP WARN] Sequence gap detected: missed %u (expected %u, got %u)\n",
                          udp_stats.missed_count, udp_stats.expected_seq, udp_stats.received_seq);
        }
        Serial.printf("[UDP] seq=%u  lin=%d  ang=%d  flags=0x%02X  age=%ums  rate=%.1fHz\n",
                      udp_pkt.seq, udp_pkt.linear, udp_pkt.angular, udp_pkt.flags, udp_stats.age_ms, udp_stats.rate_hz);

        g_latest_pkt = udp_pkt;
        g_latest_pkt_time_ms = now_ms;
        g_latest_transport = TRANSPORT_UDP;
        g_active_packet_rate_hz = udp_stats.rate_hz;
        g_has_packet = true;
    }

    // Process WebSocket packet arrival (most recent wins)
    if (ws_received) {
        if (ws_stats.has_gap) {
            Serial.printf("[WS WARN] Sequence gap detected: missed %u (expected %u, got %u)\n",
                          ws_stats.missed_count, ws_stats.expected_seq, ws_stats.received_seq);
        }
        Serial.printf("[WS] seq=%u  lin=%d  ang=%d  flags=0x%02X  age=%ums  rate=%.1fHz\n",
                      ws_pkt.seq, ws_pkt.linear, ws_pkt.angular, ws_pkt.flags, ws_stats.age_ms, ws_stats.rate_hz);

        g_latest_pkt = ws_pkt;
        g_latest_pkt_time_ms = now_ms;
        g_latest_transport = TRANSPORT_WS;
        g_active_packet_rate_hz = ws_stats.rate_hz;
        g_has_packet = true;
    }

    // Periodic WebSocket cleanup
    ws_receiver_cleanup();

    // Check for E-Stop and Fun Trick triggers on newly received packet
    if (udp_received || ws_received) {
        // E-Stop aborts trick immediately
        if (g_latest_pkt.flags & MOTION_FLAG_ESTOP) {
            trick_sequencer_abort();
        }

        // Fun Trick trigger on rising edge
        bool trick_flag = (g_latest_pkt.flags & MOTION_FLAG_FUN_TRICK) != 0;
        if (trick_flag && !g_prev_trick_flag) {
            trick_sequencer_trigger(now_ms);
            Serial.println(F("[TRICK] Fun trick triggered! Initiating 1.5s canned spin..."));
        }
        g_prev_trick_flag = trick_flag;
    }

    // Step 3: Unified 400ms fail-safe timeout check
    uint32_t age_ms = (g_latest_pkt_time_ms == 0) ? UINT32_MAX : (now_ms - g_latest_pkt_time_ms);
    bool is_timeout = (age_ms > 400);

    // Update trick sequencer countdown
    trick_sequencer_update(now_ms);
    bool trick_active = isTrickActive();

    // Determine active incoming command
    MotionCommand rawCommand = {0, 0};
    uint8_t active_flags = 0;
    if (!is_timeout && g_has_packet && !(g_latest_pkt.flags & MOTION_FLAG_ESTOP)) {
        rawCommand.linear = g_latest_pkt.linear;
        rawCommand.angular = g_latest_pkt.angular;
        active_flags = g_latest_pkt.flags;
    }

    // Step 3a: Apply speed mode scaling (Turbo / Precision)
    MotionCommand scaledCommand = applySpeedMode(rawCommand, active_flags);

    // Step 3b: Determine active command (trick sequencer overrides if active, unscaled)
    MotionCommand activeCommand = scaledCommand;
    if (trick_active) {
        activeCommand = trick_sequencer_get_command();
    }

    // Step 4: Route active command through collision filter (trick & speed modes ALWAYS filtered!)
    MotionCommand safeCommand = applyCollisionFilter(activeCommand);

    // Step 5: Drive motors with safe filtered velocities
    driveMotors(safeCommand.linear, safeCommand.angular);

    if (safeCommand.linear != 0 || safeCommand.angular != 0) {
        int16_t left = (int16_t)safeCommand.linear + (int16_t)safeCommand.angular;
        int16_t right = (int16_t)safeCommand.linear - (int16_t)safeCommand.angular;
        if (left > 100) left = 100; else if (left < -100) left = -100;
        if (right > 100) right = 100; else if (right < -100) right = -100;
        const char *mode_name = getSpeedModeName(active_flags);
        Serial.printf("[MOTOR] Left: %d%% (PWM %u) | Right: %d%% (PWM %u)%s%s%s\n",
                      left, (abs(left) * 255) / 100,
                      right, (abs(right) * 255) / 100,
                      trick_active ? " [TRICK ACTIVE]" : "",
                      (mode_name && mode_name[0]) ? " [" : "",
                      (mode_name && mode_name[0]) ? mode_name : "",
                      (mode_name && mode_name[0]) ? "]" : "");
    }

    // Failsafe timeout diagnostic log (once per second)
    if (is_timeout && !trick_active) {
        if (now_ms - g_last_timeout_log_ms >= 1000) {
            if (age_ms == UINT32_MAX) {
                Serial.println(F("[FAILSAFE] No signal from either transport: waiting for initial packets..."));
            } else {
                Serial.printf("[FAILSAFE] No signal from controller: packet age %ums > 400ms timeout\n", age_ms);
            }
            g_last_timeout_log_ms = now_ms;
        }
    }

    // Step 6: Update OLED debug display (~5Hz rate-limited)
    char ip_str[24];
    snprintf(ip_str, sizeof(ip_str), "%s", WiFi.localIP().toString().c_str());

    const char *transport_str = "NONE";
    if (g_latest_transport == TRANSPORT_WS) transport_str = "WS";
    else if (g_latest_transport == TRANSPORT_UDP) transport_str = "UDP";

    OledTelemetryData telem;
    telem.wifi_ip = ip_str;
    telem.wifi_connected = (WiFi.status() == WL_CONNECTED);
    telem.packet_rate_hz = g_active_packet_rate_hz;
    telem.signal_timeout = is_timeout;
    telem.in_linear = activeCommand.linear;
    telem.in_angular = activeCommand.angular;
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
    telem.active_transport = transport_str;
    telem.speed_mode = getSpeedModeName(active_flags);

    oled_debug_update(&telem, now_ms, false);

    // Yield control loop throttle
    delay(2);
}
