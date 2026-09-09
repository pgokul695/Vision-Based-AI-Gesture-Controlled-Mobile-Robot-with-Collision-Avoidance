/**
 * @file udp_receiver.cpp
 * @brief Non-blocking UDP packet receiver implementation for ESP32.
 */

#include "network/udp_receiver.h"
#include <Arduino.h>
#include <WiFiUdp.h>

#define RATE_WINDOW_SIZE 20

static WiFiUDP g_udp;
static uint16_t g_port = DEFAULT_ROBOT_UDP_PORT;
static bool g_is_listening = false;

static uint32_t g_last_packet_rx_ms = 0;
static MotionPacket g_last_valid_packet = {0};
static bool g_has_received_packet = false;
static uint16_t g_expected_seq = 0;

// Rolling packet rate estimation window
static uint32_t g_rx_timestamps[RATE_WINDOW_SIZE] = {0};
static uint8_t g_rx_count = 0;
static uint8_t g_rx_head = 0;
static float g_latest_rate_hz = 0.0f;

bool udp_receiver_init(const UdpReceiverConfig *config) {
    if (config && config->listen_port > 0) {
        g_port = config->listen_port;
    } else {
        g_port = DEFAULT_ROBOT_UDP_PORT;
    }

    if (g_is_listening) {
        g_udp.stop();
        g_is_listening = false;
    }

    // Reset statistics
    g_last_packet_rx_ms = 0;
    g_has_received_packet = false;
    g_expected_seq = 0;
    g_rx_count = 0;
    g_rx_head = 0;
    g_latest_rate_hz = 0.0f;

    uint8_t success = g_udp.begin(g_port);
    if (success) {
        g_is_listening = true;
        Serial.printf("[UDP] Listening for MotionPackets on port %u\n", g_port);
        return true;
    } else {
        Serial.printf("[UDP ERROR] Failed to bind to port %u\n", g_port);
        return false;
    }
}

bool udp_receiver_poll(MotionPacket *out_pkt, uint32_t current_time_ms) {
    return udp_receiver_poll_stats(out_pkt, NULL, current_time_ms);
}

bool udp_receiver_poll_stats(MotionPacket *out_pkt, UdpPacketStats *out_stats, uint32_t current_time_ms) {
    if (!out_pkt || !g_is_listening) {
        return false;
    }

    int packet_size = g_udp.parsePacket();
    if (packet_size <= 0) {
        return false;
    }

    // Reject packet if size does not match exact protocol specification
    if (packet_size != (int)sizeof(MotionPacket)) {
        // Drain invalid packet payload from socket buffer
        uint8_t discard_buf[64];
        while (g_udp.available() > 0) {
            g_udp.read(discard_buf, sizeof(discard_buf));
        }

        Serial.printf("[UDP ERROR] Invalid packet size: received %d bytes (expected %d) from %s:%u\n",
                      packet_size,
                      (int)sizeof(MotionPacket),
                      g_udp.remoteIP().toString().c_str(),
                      g_udp.remotePort());
        return false;
    }

    // Read full packet payload
    uint8_t rx_buf[sizeof(MotionPacket)];
    int bytes_read = g_udp.read(rx_buf, sizeof(rx_buf));
    if (bytes_read != (int)sizeof(MotionPacket)) {
        Serial.printf("[UDP ERROR] Short read: got %d bytes (expected %d)\n",
                      bytes_read,
                      (int)sizeof(MotionPacket));
        return false;
    }

    // Unpack and validate packet integrity using protocol validator
    MotionPacket candidate;
    memcpy(&candidate, rx_buf, sizeof(MotionPacket));

    if (!motion_packet_is_valid(&candidate)) {
        Serial.printf("[UDP ERROR] Packet validation failed: magic=0x%02X (exp 0x%02X), ver=%u (exp %u) from %s:%u\n",
                      candidate.magic,
                      MOTION_PACKET_MAGIC,
                      candidate.version,
                      MOTION_PACKET_VERSION,
                      g_udp.remoteIP().toString().c_str(),
                      g_udp.remotePort());
        return false;
    }

    // Packet is structurally intact and valid
    *out_pkt = candidate;

    // Calculate time elapsed since previous valid packet
    uint32_t age_ms = 0;
    if (g_has_received_packet) {
        if (current_time_ms >= g_last_packet_rx_ms) {
            age_ms = current_time_ms - g_last_packet_rx_ms;
        }
    }

    // Update sliding-window rolling rate estimate
    if (g_rx_count > 0) {
        uint8_t oldest_idx = (g_rx_head - g_rx_count + RATE_WINDOW_SIZE) % RATE_WINDOW_SIZE;
        uint32_t window_dt_ms = current_time_ms - g_rx_timestamps[oldest_idx];
        if (window_dt_ms > 0) {
            g_latest_rate_hz = ((float)g_rx_count * 1000.0f) / (float)window_dt_ms;
        }
    }
    g_rx_timestamps[g_rx_head] = current_time_ms;
    g_rx_head = (g_rx_head + 1) % RATE_WINDOW_SIZE;
    if (g_rx_count < RATE_WINDOW_SIZE) {
        g_rx_count++;
    }

    // Sequence tracking and drop/reorder detection
    bool has_gap = false;
    uint16_t missed_count = 0;
    uint16_t expected_seq = g_expected_seq;

    if (g_has_received_packet) {
        if (out_pkt->seq != g_expected_seq) {
            has_gap = true;
            missed_count = (uint16_t)((out_pkt->seq - g_expected_seq) & 0xFFFF);
        }
    }

    // Update receiver state
    g_expected_seq = (uint16_t)((out_pkt->seq + 1) & 0xFFFF);
    g_last_packet_rx_ms = current_time_ms;
    g_last_valid_packet = *out_pkt;
    g_has_received_packet = true;

    // Populate diagnostic statistics if requested
    if (out_stats) {
        out_stats->age_ms = age_ms;
        out_stats->rate_hz = g_latest_rate_hz;
        out_stats->has_gap = has_gap;
        out_stats->expected_seq = expected_seq;
        out_stats->received_seq = out_pkt->seq;
        out_stats->missed_count = missed_count;
    }

    return true;
}

uint32_t udp_receiver_get_time_since_last_packet_ms(uint32_t current_time_ms) {
    if (!g_has_received_packet) {
        return UINT32_MAX;
    }
    if (current_time_ms >= g_last_packet_rx_ms) {
        return current_time_ms - g_last_packet_rx_ms;
    }
    return 0;
}

float udp_receiver_get_rolling_rate_hz(void) {
    return g_latest_rate_hz;
}

void udp_receiver_stop(void) {
    if (g_is_listening) {
        g_udp.stop();
        g_is_listening = false;
        Serial.println(F("[UDP] Receiver stopped."));
    }
}
