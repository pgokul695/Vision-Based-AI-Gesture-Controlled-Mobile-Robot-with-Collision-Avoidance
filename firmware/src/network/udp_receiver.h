/**
 * @file udp_receiver.h
 * @brief Non-blocking UDP packet receiver interface for incoming MotionPackets.
 */

#ifndef UDP_RECEIVER_H
#define UDP_RECEIVER_H

#include <stdint.h>
#include <stdbool.h>
#include "motion_packet.h"

#ifdef __cplusplus
extern "C" {
#endif

#define DEFAULT_ROBOT_UDP_PORT 5005

/**
 * @brief Configuration for the UDP receiver service.
 */
typedef struct {
    uint16_t listen_port;
} UdpReceiverConfig;

/**
 * @brief Packet reception diagnostic statistics.
 */
typedef struct {
    uint32_t age_ms;        // Time since previous valid packet (ms)
    float rate_hz;          // Rolling packet rate over last 20 packets (Hz)
    bool has_gap;           // True if sequence number gap was detected
    uint16_t expected_seq;  // Expected sequence number
    uint16_t received_seq;  // Actual received sequence number
    uint16_t missed_count;  // Count of missed/gapped packets
} UdpPacketStats;

/**
 * @brief Initializes the UDP socket listener on the specified port.
 * @param config Port configuration (or NULL for DEFAULT_ROBOT_UDP_PORT).
 * @return true if socket successfully opened, false otherwise.
 */
bool udp_receiver_init(const UdpReceiverConfig *config);

/**
 * @brief Polls the UDP socket for newly arrived packets.
 *
 * Discards and logs packets that fail length, magic, or version checks.
 *
 * @param out_pkt Pointer to MotionPacket struct populated if a new packet arrived.
 * @param current_time_ms System timestamp in ms.
 * @return true if a valid new packet was received, false otherwise.
 */
bool udp_receiver_poll(MotionPacket *out_pkt, uint32_t current_time_ms);

/**
 * @brief Polls the UDP socket for newly arrived packets and populates diagnostic stats.
 *
 * @param out_pkt Pointer to MotionPacket struct populated if a new packet arrived.
 * @param out_stats Pointer to UdpPacketStats populated with reception stats.
 * @param current_time_ms System timestamp in ms.
 * @return true if a valid new packet was received, false otherwise.
 */
bool udp_receiver_poll_stats(MotionPacket *out_pkt, UdpPacketStats *out_stats, uint32_t current_time_ms);

/**
 * @brief Returns the duration in milliseconds since the last valid packet was received.
 * @param current_time_ms System timestamp in ms.
 * @return Milliseconds elapsed since last valid packet, or UINT32_MAX if no packet received yet.
 */
uint32_t udp_receiver_get_time_since_last_packet_ms(uint32_t current_time_ms);

/**
 * @brief Returns the latest rolling packet reception rate in Hz.
 */
float udp_receiver_get_rolling_rate_hz(void);

/**
 * @brief Closes the UDP socket.
 */
void udp_receiver_stop(void);

#ifdef __cplusplus
}
#endif

#endif // UDP_RECEIVER_H
