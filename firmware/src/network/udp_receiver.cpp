/**
 * @file udp_receiver.cpp
 * @brief Stub implementation of non-blocking UDP receiver for ESP32.
 */

#include "network/udp_receiver.h"

static uint16_t g_port = 8888;
static uint32_t g_last_packet_rx_ms = 0;
static MotionPacket g_last_valid_packet = {0};
static bool g_has_received_packet = false;

bool udp_receiver_init(const UdpReceiverConfig *config) {
    if (config) {
        g_port = config->listen_port;
    }

    // TODO: Initialize WiFiUDP instance or lwIP socket
    // TODO: Bind to UDP port (g_port)
    (void)g_port;
    return true;
}

bool udp_receiver_poll(MotionPacket *out_pkt, uint32_t current_time_ms) {
    if (!out_pkt) {
        return false;
    }

    // TODO: Check if packet is available (e.g., udp.parsePacket())
    // TODO: Read payload into a 10-byte buffer
    // TODO: Call parse_motion_packet(buffer, len, out_pkt)
    // TODO: Check sequence number to ignore old / out-of-order packets
    // If valid:
    //   g_last_valid_packet = *out_pkt;
    //   g_last_packet_rx_ms = current_time_ms;
    //   g_has_received_packet = true;
    //   return true;

    (void)current_time_ms;
    return false;
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

void udp_receiver_stop(void) {
    // TODO: Close UDP socket / udp.stop()
}
