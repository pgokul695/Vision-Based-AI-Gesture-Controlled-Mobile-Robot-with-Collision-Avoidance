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

### A. Motor Drivers (Dual Parallel-Wired L298N)
The two L298N boards have their logic control pins wired in parallel to the same 6 ESP32 GPIOs:
- Board 1 (Front): Left channel = Front-Left Motor, Right channel = Front-Right Motor
- Board 2 (Rear): Left channel = Rear-Left Motor, Right channel = Rear-Right Motor

| Driver Signal | ESP32 Pin | Function | Parallel Connected Loads |
|---------------|-----------|----------|--------------------------|
| `ENA` (PWM)   | `GPIO 13` | Left Speed Control (LEDC CH0) | Both L298Ns ENA pins |
| `IN1`         | `GPIO 12` | Left Direction A | Both L298Ns IN1 pins |
| `IN2`         | `GPIO 14` | Left Direction B | Both L298Ns IN2 pins |
| `ENB` (PWM)   | `GPIO 25` | Right Speed Control (LEDC CH1) | Both L298Ns ENB pins |
| `IN3`         | `GPIO 27` | Right Direction A | Both L298Ns IN3 pins |
| `IN4`         | `GPIO 26` | Right Direction B | Both L298Ns IN4 pins |
| `VCC`         | `9V` Rail | Motor Power Supply | Both L298N 12V/VCC screw terminals |
| `GND`         | `GND Bus` | Common Ground | Both L298N GND terminals + ESP32 GND |

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
