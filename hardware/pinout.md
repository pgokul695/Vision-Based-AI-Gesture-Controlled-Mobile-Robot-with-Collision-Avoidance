# ESP32 Pinout Allocation Table

This document details the GPIO assignments for the ESP32-WROOM-32 Dev Module. All allocations are selected to avoid boot strapping conflicts (avoiding GPIO 0, 2, 12, and 15).

| GPIO Pin | Direction | Connected Subsystem | Signal Function | Remarks |
|----------|-----------|---------------------|-----------------|---------|
| `GPIO 4` | OUTPUT | Motor Driver | Right Motor PWM (ENB) | LEDC Channel 1 |
| `GPIO 5` | OUTPUT | Ultrasonic Left | Trigger Pulse | ~45° Front-Left |
| `GPIO 13` | OUTPUT | Motor Driver | Right Motor IN4 | Direction B |
| `GPIO 14` | OUTPUT | Motor Driver | Right Motor IN3 | Direction A |
| `GPIO 16` | INPUT | IR Proximity | Rear-Center Digital Read | Active LOW |
| `GPIO 18` | INPUT | Ultrasonic Left | Echo Return | Use 3.3V logic or divider |
| `GPIO 19` | OUTPUT | Ultrasonic Center | Trigger Pulse | 0° Front-Center |
| `GPIO 21` | INPUT | Ultrasonic Center | Echo Return | Use 3.3V logic or divider |
| `GPIO 22` | OUTPUT | Ultrasonic Right | Trigger Pulse | ~45° Front-Right |
| `GPIO 23` | INPUT | Ultrasonic Right | Echo Return | Use 3.3V logic or divider |
| `GPIO 25` | OUTPUT | Motor Driver | Left Motor IN1 | Direction A |
| `GPIO 26` | OUTPUT | Motor Driver | Left Motor IN2 | Direction B |
| `GPIO 27` | OUTPUT | Motor Driver | Left Motor PWM (ENA) | LEDC Channel 0 |
| `GPIO 32` | INPUT | IR Proximity | Front-Left Digital Read | Low-mounted front |
| `GPIO 33` | INPUT | IR Proximity | Front-Right Digital Read | Low-mounted front |
| `GPIO 34` | INPUT | IR Proximity | Side-Left Digital Read | ESP32 Input-only pin (no pullup) |
| `GPIO 35` | INPUT | IR Proximity | Side-Right Digital Read | ESP32 Input-only pin (no pullup) |

## Strapping Pin Precautions
The following pins are intentionally **UNASSIGNED** to guarantee reliable bootloader and flashing behavior:
- `GPIO 0`: Boot mode selector (Must be pulled HIGH for normal boot)
- `GPIO 2`: Internal strapping pin (Connected to on-board LED on some modules)
- `GPIO 12` (MTDI): Flash voltage strapping (Driving HIGH at boot can cause boot failure)
- `GPIO 15` (MTDO): JTAG strapping / silent boot output
