# ESP32 Pinout Allocation Table

This document details the GPIO assignments for the ESP32-WROOM-32 Dev Module with a 4WD skid-steer chassis, dual parallel-wired L298N motor drivers, 3x ultrasonic sensors, 5x digital IR proximity sensors, and an SSD1306 OLED debug display.

## Motor Drivetrain Pinout (Dual Parallel-Wired L298N)

The two L298N drivers have their control inputs wired in parallel to the same 6 ESP32 GPIOs. Each motor has its own H-bridge channel, but both left channels and both right channels receive the same control signals simultaneously.

| GPIO Pin | Direction | Connected Subsystem | Signal Function | Remarks |
|----------|-----------|---------------------|-----------------|---------|
| `GPIO 13` | OUTPUT | Dual L298N (Parallel) | Left Side Speed (`ENA` PWM) | LEDC Channel 0 (1 kHz, 8-bit) |
| `GPIO 12` | OUTPUT | Dual L298N (Parallel) | Left Side Direction (`IN1`) | Strapping pin (normal output post-boot) |
| `GPIO 14` | OUTPUT | Dual L298N (Parallel) | Left Side Direction (`IN2`) | Direction control |
| `GPIO 25` | OUTPUT | Dual L298N (Parallel) | Right Side Speed (`ENB` PWM) | LEDC Channel 1 (1 kHz, 8-bit) |
| `GPIO 27` | OUTPUT | Dual L298N (Parallel) | Right Side Direction (`IN3`) | Direction control |
| `GPIO 26` | OUTPUT | Dual L298N (Parallel) | Right Side Direction (`IN4`) | Direction control |

## Ultrasonic Sensor Array (3x Front, Non-Blocking Round-Robin)

Fired sequentially in round-robin sequence (never simultaneously) with a bounded 25ms timeout.

| Position | Trig Pin | Echo Pin | Remarks |
|----------|----------|----------|---------|
| Front-Left | `GPIO 15` (OUTPUT) | `GPIO 2` (INPUT) | ~45° Front-Left |
| Front-Center | `GPIO 23` (OUTPUT) | `GPIO 35` (INPUT) | 0° Front-Center (swapped with D34) |
| Front-Right | `GPIO 33` (OUTPUT) | `GPIO 32` (INPUT) | ~45° Front-Right |

## Digital IR Proximity Sensors (5x, Polled Every Loop)

Digital obstacle detection modules (active-low: `LOW` = obstacle detected).

| Position | GPIO Pin | Direction | Remarks |
|----------|----------|-----------|---------|
| Front-Left | `GPIO 34` | INPUT | Swapped with D23; GPI pin without internal pullup |
| Front-Right | `GPIO 5` | INPUT_PULLUP | Active LOW |
| Side-Left | `GPIO 19` | INPUT_PULLUP | Active LOW (gates left turn) |
| Side-Right | `GPIO 4` | INPUT_PULLUP | Active LOW (gates right turn) |
| Rear-Center | `GPIO 18` | INPUT_PULLUP | Active LOW (gates reverse) |

## OLED Debug Display (SSD1306 I2C, 128x64)

| Signal | GPIO Pin | Function | Remarks |
|--------|----------|----------|---------|
| SDA | `GPIO 21` | I2C Data | 400 kHz Fast Mode, Address `0x3C` |
| SCL | `GPIO 22` | I2C Clock | 400 kHz Fast Mode |

## Strapping Pin Precautions
- `GPIO 0`: Boot mode selector (Pulled HIGH for normal boot)
- `GPIO 2`: Internal strapping pin / FL Echo. Do not pull HIGH externally during boot.
- `GPIO 12` (MTDI): Flash voltage strapping. Used as normal output (`MOTOR_LEFT_IN1_PIN`) post-boot.
- `GPIO 15` (MTDO): JTAG strapping / FL Trig. Pulled LOW by default.
