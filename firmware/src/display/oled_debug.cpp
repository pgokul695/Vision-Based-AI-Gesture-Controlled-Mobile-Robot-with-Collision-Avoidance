/**
 * @file oled_debug.cpp
 * @brief SSD1306 I2C OLED live telemetry display implementation.
 */

#include "display/oled_debug.h"
#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

static Adafruit_SSD1306 g_display(OLED_SCREEN_WIDTH, OLED_SCREEN_HEIGHT, &Wire, -1);
static bool g_oled_available = false;
static uint32_t g_last_update_ms = 0;

#define OLED_REFRESH_INTERVAL_MS 200 // ~5 Hz

bool oled_debug_init(void) {
    Wire.begin(OLED_SDA_PIN, OLED_SCL_PIN);
    Wire.setClock(400000); // 400kHz Fast Mode I2C

    // Try primary I2C address 0x3C, fallback to 0x3D
    if (g_display.begin(SSD1306_SWITCHCAPVCC, OLED_I2C_ADDRESS)) {
        g_oled_available = true;
    } else if (g_display.begin(SSD1306_SWITCHCAPVCC, 0x3D)) {
        g_oled_available = true;
    } else {
        Serial.println(F("[OLED WARN] Display not detected on I2C (SDA=21, SCL=22). Running headless."));
        g_oled_available = false;
        return false;
    }

    g_display.clearDisplay();
    g_display.setTextSize(1);
    g_display.setTextColor(SSD1306_WHITE);
    g_display.setCursor(0, 0);
    g_display.println(F("ESP32 Robot Booting..."));
    g_display.println(F("Sensors + Collision"));
    g_display.display();
    return true;
}

void oled_debug_update(const OledTelemetryData *data, uint32_t now_ms, bool force) {
    if (!g_oled_available || !data) {
        return;
    }

    if (!force && (now_ms - g_last_update_ms < OLED_REFRESH_INTERVAL_MS)) {
        return;
    }
    g_last_update_ms = now_ms;

    g_display.clearDisplay();
    g_display.setTextSize(1);
    g_display.setTextColor(SSD1306_WHITE);

    // Row 1: Wi-Fi / UDP Status
    g_display.setCursor(0, 0);
    if (!data->wifi_connected) {
        g_display.print(F("WIFI: CONNECTING..."));
    } else if (data->signal_timeout) {
        g_display.printf("%s [NO SIG]", data->wifi_ip ? data->wifi_ip : "READY");
    } else {
        g_display.printf("%s %.0fHz", data->wifi_ip ? data->wifi_ip : "", data->packet_rate_hz);
    }

    // Divider
    g_display.drawLine(0, 10, 127, 10, SSD1306_WHITE);

    // Rows 2 & 3: Commanded vs Safe Velocities
    g_display.setCursor(0, 13);
    g_display.printf("IN : L:%+4d  A:%+4d", data->in_linear, data->in_angular);

    g_display.setCursor(0, 23);
    g_display.printf("OUT: L:%+4d  A:%+4d", data->out_linear, data->out_angular);

    // Divider
    g_display.drawLine(0, 33, 127, 33, SSD1306_WHITE);

    // Row 4: Ultrasonic Array (L, C, R)
    char us_l[6], us_c[6], us_r[6];
    if (data->us_left_stale || data->us_left_cm < 0) {
        snprintf(us_l, sizeof(us_l), "--");
    } else {
        snprintf(us_l, sizeof(us_l), "%d", (int)data->us_left_cm);
    }

    if (data->us_center_stale || data->us_center_cm < 0) {
        snprintf(us_c, sizeof(us_c), "--");
    } else {
        snprintf(us_c, sizeof(us_c), "%d", (int)data->us_center_cm);
    }

    if (data->us_right_stale || data->us_right_cm < 0) {
        snprintf(us_r, sizeof(us_r), "--");
    } else {
        snprintf(us_r, sizeof(us_r), "%d", (int)data->us_right_cm);
    }

    g_display.setCursor(0, 36);
    g_display.printf("US: L:%s C:%s R:%s", us_l, us_c, us_r);

    // Rows 5 & 6: 5-IR Status Matrix
    // '!' represents obstacle detected; '.' represents clear
    g_display.setCursor(0, 47);
    g_display.printf("IR: %c  %c  %c  %c  %c",
        data->ir_fl ? '!' : '.',
        data->ir_fr ? '!' : '.',
        data->ir_sl ? '!' : '.',
        data->ir_sr ? '!' : '.',
        data->ir_rc ? '!' : '.');

    g_display.setCursor(0, 56);
    g_display.print(F("   FL FR SL SR RC"));

    g_display.display();
}
