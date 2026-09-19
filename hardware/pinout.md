# ESP32 Pinout Allocation Table

This document details the GPIO assignments for the ESP32-WROOM-32 Dev Module with a 4WD skid-steer chassis and dual parallel-wired L298N motor drivers.

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

## Sensor Subsystems (Future Integration)

| GPIO Pin | Direction | Connected Subsystem | Signal Function | Remarks |
|----------|-----------|---------------------|-----------------|---------|
| `GPIO 5` | OUTPUT | Ultrasonic Left | Trigger Pulse | ~45° Front-Left |
| `GPIO 18` | INPUT | Ultrasonic Left | Echo Return | Use 3.3V logic or divider |
| `GPIO 19` | OUTPUT | Ultrasonic Center | Trigger Pulse | 0° Front-Center |
| `GPIO 21` | INPUT | Ultrasonic Center | Echo Return | Use 3.3V logic or divider |
| `GPIO 22` | OUTPUT | Ultrasonic Right | Trigger Pulse | ~45° Front-Right |
| `GPIO 23` | INPUT | Ultrasonic Right | Echo Return | Use 3.3V logic or divider |
| `GPIO 16` | INPUT | IR Proximity | Rear-Center Digital Read | Active LOW |
| `GPIO 32` | INPUT | IR Proximity | Front-Left Digital Read | Low-mounted front |
| `GPIO 33` | INPUT | IR Proximity | Front-Right Digital Read | Low-mounted front |
| `GPIO 34` | INPUT | IR Proximity | Side-Left Digital Read | ESP32 Input-only pin (no pullup) |
| `GPIO 35` | INPUT | IR Proximity | Side-Right Digital Read | ESP32 Input-only pin (no pullup) |

## Strapping Pin Precautions
- `GPIO 0`: Boot mode selector (Must be pulled HIGH for normal boot)
- `GPIO 2`: Internal strapping pin (Connected to on-board LED / status LED)
- `GPIO 12` (MTDI): Flash voltage strapping. Used as normal output (`MOTOR_LEFT_IN1_PIN`) post-boot. If flaky boots ever occur, check that L298N logic does not pull this line HIGH during boot.
- `GPIO 15` (MTDO): JTAG strapping / silent boot output
