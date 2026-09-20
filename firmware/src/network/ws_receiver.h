/**
 * @file ws_receiver.h
 * @brief Asynchronous WebSocket receiver interface for MotionPackets.
 */

#ifndef WS_RECEIVER_H
#define WS_RECEIVER_H

#include <stdint.h>
#include <stdbool.h>
#include "motion_packet.h"
#include "network/udp_receiver.h"

#ifdef __cplusplus
extern "C" {
#endif

#define DEFAULT_ROBOT_WS_PORT 80
#define DEFAULT_ROBOT_WS_PATH "/ws"

typedef struct {
    uint16_t listen_port;
    const char *ws_path;
} WsReceiverConfig;

typedef UdpPacketStats WsPacketStats;

/**
 * @brief Initializes the AsyncWebServer and AsyncWebSocket server.
 * @param config Port and endpoint configuration (or NULL for defaults: 80, "/ws").
 * @return true if successfully started, false otherwise.
 */
bool ws_receiver_init(const WsReceiverConfig *config);

/**
 * @brief Polls whether a new valid MotionPacket arrived over WebSocket.
 * Non-blocking.
 *
 * @param out_pkt Pointer to MotionPacket struct populated if a packet arrived.
 * @param current_time_ms Current system timestamp.
 * @return true if a valid new packet arrived, false otherwise.
 */
bool ws_receiver_poll(MotionPacket *out_pkt, uint32_t current_time_ms);

/**
 * @brief Polls whether a new valid MotionPacket arrived and populates diagnostic statistics.
 *
 * @param out_pkt Pointer to MotionPacket struct populated if a packet arrived.
 * @param out_stats Pointer to WsPacketStats struct populated with packet metrics.
 * @param current_time_ms Current system timestamp.
 * @return true if a valid new packet arrived, false otherwise.
 */
bool ws_receiver_poll_stats(MotionPacket *out_pkt, WsPacketStats *out_stats, uint32_t current_time_ms);

/**
 * @brief Returns time in milliseconds since the last valid WebSocket packet arrived.
 * Returns UINT32_MAX if no packet has ever been received.
 */
uint32_t ws_receiver_get_time_since_last_packet_ms(uint32_t current_time_ms);

/**
 * @brief Returns the number of currently active connected WebSocket clients.
 */
uint32_t ws_receiver_get_client_count(void);

/**
 * @brief Cleans up disconnected WebSocket clients. Call periodically in loop().
 */
void ws_receiver_cleanup(void);

#ifdef __cplusplus
}
#endif

#endif // WS_RECEIVER_H
