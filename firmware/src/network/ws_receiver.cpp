/**
 * @file ws_receiver.cpp
 * @brief Asynchronous WebSocket receiver implementation for MotionPackets.
 */

#include "network/ws_receiver.h"
#include "network/web_server_content.h"
#include <Arduino.h>
#include <ESPAsyncWebServer.h>
#include <AsyncTCP.h>
#include <string.h>

static AsyncWebServer *g_server = nullptr;
static AsyncWebSocket *g_ws = nullptr;

static MotionPacket g_latest_ws_pkt;
static volatile bool g_new_packet = false;
static uint32_t g_last_packet_time_ms = 0;
static WsPacketStats g_stats = {0};

static uint32_t g_rolling_ts[20] = {0};
static uint8_t g_rolling_head = 0;
static uint8_t g_rolling_count = 0;
static uint16_t g_expected_seq = 0;
static bool g_seq_initialized = false;

static void on_ws_event(AsyncWebSocket *server, AsyncWebSocketClient *client,
                        AwsEventType type, void *arg, uint8_t *data, size_t len)
{
    (void)server;

    switch (type) {
        case WS_EVT_CONNECT:
            Serial.printf("[WS] Client #%u connected from %s\n",
                          client->id(), client->remoteIP().toString().c_str());
            break;

        case WS_EVT_DISCONNECT:
            Serial.printf("[WS] Client #%u disconnected\n", client->id());
            break;

        case WS_EVT_DATA: {
            AwsFrameInfo *info = (AwsFrameInfo*)arg;
            if (info->final && info->index == 0 && info->len == len) {
                if (info->opcode == WS_BINARY) {
                    if (len != sizeof(MotionPacket)) {
                        Serial.printf("[WS ERROR] Invalid packet size: %u bytes from client #%u (expected %u)\n",
                                      (unsigned)len, client->id(), (unsigned)sizeof(MotionPacket));
                        return;
                    }

                    MotionPacket pkt;
                    memcpy(&pkt, data, sizeof(MotionPacket));

                    if (!motion_packet_is_valid(&pkt)) {
                        Serial.printf("[WS ERROR] Packet validation failure from client #%u: magic=0x%02X ver=%u\n",
                                      client->id(), pkt.magic, pkt.version);
                        return;
                    }

                    uint32_t now_ms = millis();
                    g_latest_ws_pkt = pkt;
                    g_new_packet = true;
                    g_last_packet_time_ms = now_ms;

                    // Sequence continuity check
                    g_stats.has_gap = false;
                    g_stats.received_seq = pkt.seq;
                    if (g_seq_initialized) {
                        if (pkt.seq != g_expected_seq) {
                            uint16_t diff = (pkt.seq - g_expected_seq);
                            g_stats.has_gap = true;
                            g_stats.missed_count = diff;
                            g_stats.expected_seq = g_expected_seq;
                        }
                    } else {
                        g_seq_initialized = true;
                    }
                    g_expected_seq = (pkt.seq + 1);

                    // Rate calculation rolling buffer (last 20 packets)
                    g_rolling_ts[g_rolling_head] = now_ms;
                    g_rolling_head = (g_rolling_head + 1) % 20;
                    if (g_rolling_count < 20) {
                        g_rolling_count++;
                    }
                    if (g_rolling_count >= 2) {
                        uint8_t oldest_idx = (g_rolling_head + 20 - g_rolling_count) % 20;
                        uint32_t delta_ms = now_ms - g_rolling_ts[oldest_idx];
                        if (delta_ms > 0) {
                            g_stats.rate_hz = ((g_rolling_count - 1) * 1000.0f) / (float)delta_ms;
                        }
                    }
                } else {
                    Serial.printf("[WS WARN] Unexpected non-binary frame (%u bytes) from client #%u\n",
                                  (unsigned)len, client->id());
                }
            }
            break;
        }

        case WS_EVT_ERROR:
            Serial.printf("[WS ERROR] Client #%u error (%u)\n", client->id(), *((uint16_t*)arg));
            break;

        default:
            break;
    }
}

bool ws_receiver_init(const WsReceiverConfig *config) {
    uint16_t port = config ? config->listen_port : DEFAULT_ROBOT_WS_PORT;
    const char *path = (config && config->ws_path) ? config->ws_path : DEFAULT_ROBOT_WS_PATH;

    if (!g_server) {
        g_server = new AsyncWebServer(port);
    }
    if (!g_ws) {
        g_ws = new AsyncWebSocket(path);
    }

    g_ws->onEvent(on_ws_event);
    g_server->addHandler(g_ws);
    register_web_app_routes(g_server);
    g_server->begin();

    Serial.printf("[WS] WebSocket receiver listening on port %u at %s\n", port, path);
    return true;
}

bool ws_receiver_poll(MotionPacket *out_pkt, uint32_t current_time_ms) {
    return ws_receiver_poll_stats(out_pkt, nullptr, current_time_ms);
}

bool ws_receiver_poll_stats(MotionPacket *out_pkt, WsPacketStats *out_stats, uint32_t current_time_ms) {
    if (!g_new_packet) {
        return false;
    }

    g_new_packet = false;

    if (out_pkt) {
        *out_pkt = g_latest_ws_pkt;
    }

    if (out_stats) {
        *out_stats = g_stats;
        out_stats->age_ms = ws_receiver_get_time_since_last_packet_ms(current_time_ms);
    }

    return true;
}

uint32_t ws_receiver_get_time_since_last_packet_ms(uint32_t current_time_ms) {
    if (g_last_packet_time_ms == 0) {
        return UINT32_MAX;
    }
    if (current_time_ms >= g_last_packet_time_ms) {
        return current_time_ms - g_last_packet_time_ms;
    }
    return 0;
}

uint32_t ws_receiver_get_client_count(void) {
    if (g_ws) {
        return g_ws->count();
    }
    return 0;
}

void ws_receiver_cleanup(void) {
    if (g_ws) {
        g_ws->cleanupClients();
    }
}
