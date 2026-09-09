/**
 * @file main.cpp
 * @brief ESP32 Basic Connectivity Test firmware.
 *
 * Validates Wi-Fi connection, UDP socket binding, and MotionPacket reception
 * before integrating sensor and motor drivers.
 *
 * LED Status Indicators:
 * - Connecting to Wi-Fi: Fast blink (~5 Hz, 100ms toggle)
 * - Connected & Receiving Packets (<400ms): Slow heartbeat (~1 Hz, 500ms toggle)
 * - Signal Timeout (>400ms without packet): Rapid double-blink
 */

#include <Arduino.h>
#include <WiFi.h>
#include "motion_packet.h"
#include "network/wifi_credentials.h"
#include "network/udp_receiver.h"

// Configuration
#define ROBOT_UDP_PORT 5005

#ifndef STATUS_LED_PIN
#ifdef LED_BUILTIN
#define STATUS_LED_PIN LED_BUILTIN
#else
#define STATUS_LED_PIN 2
#endif
#endif

// LED diagnostic states
enum LedState {
    LED_STATE_CONNECTING,  // Fast blink (~5 Hz)
    LED_STATE_RECEIVING,   // Slow heartbeat (~1 Hz)
    LED_STATE_TIMEOUT      // Rapid double-blink
};

static uint32_t g_last_timeout_log_ms = 0;

/**
 * @brief Updates the status LED without blocking the execution loop.
 */
static void update_status_led(LedState state, uint32_t now_ms) {
    bool led_on = false;
    switch (state) {
        case LED_STATE_CONNECTING: {
            // ~5 Hz fast blink (100ms ON, 100ms OFF)
            led_on = (now_ms % 200) < 100;
            break;
        }
        case LED_STATE_RECEIVING: {
            // ~1 Hz slow heartbeat (500ms ON, 500ms OFF)
            led_on = (now_ms % 1000) < 500;
            break;
        }
        case LED_STATE_TIMEOUT: {
            // Rapid double-blink pattern in a 1000ms window:
            // 80ms ON, 80ms OFF, 80ms ON, 760ms OFF
            uint32_t phase = now_ms % 1000;
            if (phase < 80) {
                led_on = true;
            } else if (phase < 160) {
                led_on = false;
            } else if (phase < 240) {
                led_on = true;
            } else {
                led_on = false;
            }
            break;
        }
    }
    digitalWrite(STATUS_LED_PIN, led_on ? HIGH : LOW);
}

/**
 * @brief Connects to Wi-Fi with visible LED feedback and 15s timeout retry loop.
 */
static void connect_wifi(void) {
    WiFi.mode(WIFI_STA);

    while (true) {
        Serial.printf("[WIFI] Connecting to SSID: \"%s\" ...\n", WIFI_SSID);
        WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

        uint32_t start_ms = millis();
        const uint32_t timeout_ms = 15000;

        while (WiFi.status() != WL_CONNECTED && (millis() - start_ms < timeout_ms)) {
            update_status_led(LED_STATE_CONNECTING, millis());
            delay(10);
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
        uint32_t retry_wait = millis();
        while (millis() - retry_wait < 2000) {
            update_status_led(LED_STATE_CONNECTING, millis());
            delay(10);
        }
    }
}

void setup() {
    Serial.begin(115200);
    delay(500);

    pinMode(STATUS_LED_PIN, OUTPUT);
    digitalWrite(STATUS_LED_PIN, LOW);

    Serial.println(F("\n=================================================="));
    Serial.println(F("  ESP32 Basic Connectivity Test (Motion UDP)"));
    Serial.println(F("=================================================="));

    // Connect to Wi-Fi network
    connect_wifi();

    // Initialize UDP receiver on configured port
    UdpReceiverConfig udp_cfg = { ROBOT_UDP_PORT };
    if (!udp_receiver_init(&udp_cfg)) {
        Serial.println(F("[FATAL] Failed to initialize UDP receiver!"));
    }

    Serial.printf("[READY] Listening on %s:%u\n", WiFi.localIP().toString().c_str(), ROBOT_UDP_PORT);
    Serial.println(F("[READY] Status LED: Slow Heartbeat = Receiving, Double-Blink = Timeout"));
    Serial.println(F("==================================================\n"));
}

void loop() {
    uint32_t now_ms = millis();

    // Check Wi-Fi connection health
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println(F("[WIFI WARN] Connection lost. Reconnecting..."));
        connect_wifi();
        return;
    }

    // 1. Non-blocking UDP packet polling
    MotionPacket pkt;
    UdpPacketStats stats;
    bool received = udp_receiver_poll_stats(&pkt, &stats, now_ms);

    if (received) {
        // Sequence gap notification (drops / out-of-order delivery)
        if (stats.has_gap) {
            Serial.printf("[WARN] Sequence gap detected: missed %u (expected %u, got %u)\n",
                          stats.missed_count, stats.expected_seq, stats.received_seq);
        }

        // Print valid packet diagnostic line matching specification:
        // [UDP] seq=123  lin=45  ang=-10  flags=0x00  age=48ms  rate=20.1Hz
        Serial.printf("[UDP] seq=%u  lin=%d  ang=%d  flags=0x%02X  age=%ums  rate=%.1fHz\n",
                      pkt.seq, pkt.linear, pkt.angular, pkt.flags, stats.age_ms, stats.rate_hz);
    }

    // 2. Failsafe timeout & liveness monitoring (>400 ms)
    uint32_t age_ms = udp_receiver_get_time_since_last_packet_ms(now_ms);

    if (age_ms > 400) {
        // Set LED to rapid double-blink timeout pattern
        update_status_led(LED_STATE_TIMEOUT, now_ms);

        // Rate-limited warning once per second (1000ms)
        if (now_ms - g_last_timeout_log_ms >= 1000) {
            if (age_ms == UINT32_MAX) {
                Serial.println(F("[FAILSAFE] No signal from controller: waiting for initial packets..."));
            } else {
                Serial.printf("[FAILSAFE] No signal from controller: packet age %ums > 400ms timeout\n", age_ms);
            }
            g_last_timeout_log_ms = now_ms;
        }
    } else {
        // Normal receiving state: slow heartbeat blink (~1 Hz)
        update_status_led(LED_STATE_RECEIVING, now_ms);
    }

    // Yield control loop throttle
    delay(2);
}
