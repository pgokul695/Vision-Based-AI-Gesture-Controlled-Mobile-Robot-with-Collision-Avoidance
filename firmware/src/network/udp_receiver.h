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

/**
 * @brief Configuration for the UDP receiver service.
 */
typedef struct {
    uint16_t listen_port;
} UdpReceiverConfig;

/**
 * @brief Initializes the UDP socket listener on the specified port.
 * @param config Port configuration.
 * @return true if socket successfully opened, false otherwise.
 */
bool udp_receiver_init(const UdpReceiverConfig *config);

/**
 * @brief Polls the UDP socket for newly arrived packets.
 *
 * Discards packets that fail length, magic, or version checks.
 *
 * @param out_pkt Pointer to MotionPacket struct populated if a new packet arrived.
 * @param current_time_ms System timestamp in ms.
 * @return true if a valid new packet was received, false otherwise.
 */
bool udp_receiver_poll(MotionPacket *out_pkt, uint32_t current_time_ms);

/**
 * @brief Returns the duration in milliseconds since the last valid packet was received.
 * @param current_time_ms System timestamp in ms.
 * @return Milliseconds elapsed since last valid packet.
 */
uint32_t udp_receiver_get_time_since_last_packet_ms(uint32_t current_time_ms);

/**
 * @brief Closes the UDP socket.
 */
void udp_receiver_stop(void);

#ifdef __cplusplus
}
#endif

#endif // UDP_RECEIVER_H
