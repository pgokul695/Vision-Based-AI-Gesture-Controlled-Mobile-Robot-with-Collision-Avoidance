# Hardware Wiring Diagram & Electrical Interconnects

This document outlines the electrical connections, power distribution rails, and signal routing between the ESP32 microcontroller, sensors, motor driver, and power subsystems.

## 1. Power Distribution

Power is supplied via a USB-C Power Delivery (PD) trigger board connected to an external USB-C power bank.

```
                  +--------------------------------+
                  |  USB-C Power Bank (PD Capable) |
                  +---------------+----------------+
                                  | USB-C Cable
                                  v
                  +---------------+----------------+
                  | USB PD Trigger Module (Set 9V) |
                  +-------+--------------+---------+
                          |              |
           9V Motor Rail  |              | 9V to VIN / 5V Buck
                          v              v
               +----------+-----+   +----+------------+
               |  Motor Driver  |   | ESP32 Dev Board |
               | (L298N/DRV8833)|   | (Internal 3.3V) |
               +-------+--------+   +----+-------+----+
                       |                 |       |
                       v                 |       v
               [2x DC Motors]            |  [3.3V / 5V Sensors]
                                         |
     COMMON GROUND BUS: -----------------+--------------------
```

### Safety & Power Notes
1. **Common Ground**: All GND pins (ESP32 GND, Motor Driver GND, Sensor GND, PD Trigger GND) must be tied together.
2. **Motor Noise Isolation**: Motors produce inductive back-EMF spikes. Use a 100uF-470uF electrolytic capacitor across the motor driver 9V power input terminals.
3. **Sensor Logic Levels**:
   - HC-SR04 ultrasonic echo lines output 5V logic. If powered from 5V, use a simple resistor voltage divider (e.g. 1kΩ / 2kΩ) on Echo $\rightarrow$ ESP32 GPIO to step down 5V to 3.3V safely (or use RCWL-1601/HC-SR04P 3.3V compatible units).
   - Digital IR sensor modules typically support 3.3V $V_{CC}$ directly.

---

## 2. Component Interconnections

### A. Motor Driver (L298N or DRV8833)
| Driver Pin | ESP32 Pin | Function |
|------------|-----------|----------|
| `IN1` | `GPIO 25` | Left Motor Direction A |
| `IN2` | `GPIO 26` | Left Motor Direction B |
| `ENA` (PWM) | `GPIO 27` | Left Motor Speed (LEDC PWM) |
| `IN3` | `GPIO 14` | Right Motor Direction A |
| `IN4` | `GPIO 13` | Right Motor Direction B |
| `ENB` (PWM) | `GPIO 4` | Right Motor Speed (LEDC PWM) |
| `VCC` | `9V` Rail | Motor Power Supply |
| `GND` | `GND Bus` | Common Ground |

### B. Front Ultrasonic Sensor Array (3x Units)
| Sensor | Trig Pin (ESP32) | Echo Pin (ESP32 via 3.3V Divider) | Angle |
|--------|------------------|------------------------------------|-------|
| Front-Left | `GPIO 5` | `GPIO 18` | ~45° Left |
| Front-Center | `GPIO 19` | `GPIO 21` | 0° Center |
| Front-Right | `GPIO 22` | `GPIO 23` | ~45° Right |

### C. Digital IR Proximity Sensors (5x Units)
| Sensor Position | ESP32 Pin | Type |
|-----------------|-----------|------|
| Front-Left (Low) | `GPIO 32` | Digital Input (Active LOW) |
| Front-Right (Low) | `GPIO 33` | Digital Input (Active LOW) |
| Side-Left (Mid) | `GPIO 34` | Digital Input (Input only) |
| Side-Right (Mid) | `GPIO 35` | Digital Input (Input only) |
| Rear-Center | `GPIO 16` | Digital Input (Active LOW) |
