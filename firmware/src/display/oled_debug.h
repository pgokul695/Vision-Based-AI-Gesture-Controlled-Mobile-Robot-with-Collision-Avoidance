/**
 * @file oled_debug.h
 * @brief SSD1306 I2C OLED live telemetry display interface.
 */

#ifndef OLED_DEBUG_H
#define OLED_DEBUG_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

#define OLED_SDA_PIN 21
#define OLED_SCL_PIN 22
#define OLED_SCREEN_WIDTH 128
#define OLED_SCREEN_HEIGHT 64
#define OLED_I2C_ADDRESS 0x3C

typedef struct {
    const char *wifi_ip;
    bool wifi_connected;
    float packet_rate_hz;
    bool signal_timeout;
    int8_t in_linear;
    int8_t in_angular;
    int8_t out_linear;
    int8_t out_angular;
    float us_left_cm;
    float us_center_cm;
    float us_right_cm;
    bool us_left_stale;
    bool us_center_stale;
    bool us_right_stale;
    bool ir_fl;
    bool ir_fr;
    bool ir_sl;
    bool ir_sr;
    bool ir_rc;
} OledTelemetryData;

/**
 * @brief Initializes I2C bus on GPIO 21/22 and connects to SSD1306 OLED.
 * @return true if successfully initialized, false otherwise.
 */
bool oled_debug_init(void);

/**
 * @brief Updates OLED display contents.
 * Throttled to ~5Hz (200ms) to avoid loading the 20Hz control loop.
 *
 * @param data Current telemetry values.
 * @param now_ms System time in milliseconds.
 * @param force If true, skips rate-limiting throttle (e.g. at boot/shutdown).
 */
void oled_debug_update(const OledTelemetryData *data, uint32_t now_ms, bool force);

#ifdef __cplusplus
}
#endif

#endif // OLED_DEBUG_H
