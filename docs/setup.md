# Setup & Development Guide

This guide covers setting up your local environment for building firmware, testing protocol packets, and running the AI gesture controller on your laptop.

---

## 1. Prerequisites

- **Python**: Version 3.10 or higher
- **C/C++ Compiler**: GCC / G++ (for local protocol unit tests)
- **Firmware Toolchain**: [PlatformIO CLI](https://platformio.org/) or the PlatformIO IDE extension for VS Code
- **Hardware**:
  - ESP32-WROOM-32 Dev Module
  - Micro-USB / USB-C data cable for flashing
  - Webcam for laptop hand tracking

---

## 2. Host Gesture Controller Setup

### A. Create and Activate Virtual Environment
```bash
cd gesture-controller
python3 -m venv .venv
source .venv/bin/activate
```

### B. Install Dependencies
```bash
pip install --upgrade pip
pip install -e ".[dev]"
```

### C. Run Host Tests
Verify that protocol serialization and hand tracker interfaces pass unit tests:
```bash
pytest
```

---

## 3. ESP32 Firmware Setup

### A. Install PlatformIO CLI (if not already installed)
```bash
pip install platformio
```

### B. Build Firmware
From the `firmware/` directory:
```bash
cd firmware
pio run
```

### C. Upload Firmware to ESP32
Connect your ESP32 to your computer via USB:
```bash
pio run --target upload
```

### D. Open Serial Monitor
```bash
pio device monitor -b 115200
```

---

## 4. Standalone Protocol & Collision Filter Tests (No Hardware Needed)

You can build and execute the C++ unit test suite locally using standard `g++`:

```bash
g++ -std=c++17 -Iprotocol -Ifirmware/src \
    firmware/src/motion/collision_filter.cpp \
    firmware/test/test_collision_filter.cpp \
    -o test_collision_filter

./test_collision_filter
```

---

## 5. Network Configuration

1. **Direct SoftAP Mode (Default)**:
   - ESP32 broadcasts a Wi-Fi Access Point (e.g. SSID: `GestureRobot-AP`, IP: `192.168.4.1`).
   - Connect your laptop to this network.
2. **Station Mode (Home / Lab Wi-Fi)**:
   - Configure your local network SSID and password in firmware.
   - Note the assigned IP output on the ESP32 Serial Monitor.

---

## 6. Running the Controller

Activate your virtual environment and launch the controller targeting the robot's IP:
```bash
cd gesture-controller
python3 src/main.py --host 192.168.4.1 --port 8888 --camera-index 0
```

---

## 7. ESP32 Basic Connectivity Test (Pre-Hardware Validation)

Before attaching motor drivers or sensors, use this test mode to verify Wi-Fi association, UDP packet validation, packet rate, and fail-safe timeout handling.

> **Note**: At this stage the ESP32 is only proving connectivity — no physical motion or sensor readings will happen yet.

### Step 1: Configure Wi-Fi Credentials
Copy the example credentials header and insert your local Wi-Fi SSID and password:
```bash
cp firmware/src/network/wifi_credentials.h.example firmware/src/network/wifi_credentials.h
```
Edit `firmware/src/network/wifi_credentials.h`:
```c
#define WIFI_SSID "YourNetworkSSID"
#define WIFI_PASSWORD "YourNetworkPassword"
```
*(This file is ignored in `.gitignore` to keep credentials secure).*

### Step 2: Build and Flash Firmware
Connect your ESP32 Dev Module via USB:
```bash
cd firmware
pio run --target upload
```

### Step 3: Find ESP32 IP from Serial Monitor
Open the serial monitor at 115200 baud:
```bash
pio device monitor -b 115200
```
On boot, you will observe the Wi-Fi connection handshake and the assigned IP address:
```
==================================================
  ESP32 Basic Connectivity Test (Motion UDP)
==================================================
[WIFI] Connecting to SSID: "YourNetworkSSID" ...
[WIFI] Connected successfully!
[WIFI] Assigned IP address: 192.168.1.150
[WIFI] Signal strength (RSSI): -52 dBm
[UDP] Listening for MotionPackets on port 5005
[READY] Listening on 192.168.1.150:5005
[READY] Status LED: Slow Heartbeat = Receiving, Double-Blink = Timeout
==================================================
```

### Step 4: Stream Packets from Gesture Controller
From a terminal on your laptop, run the gesture controller targeting the ESP32 IP and port `5005`:
```bash
cd gesture-controller
python3 src/main.py --host <esp32-ip> --port 5005
```

### Step 5: Verify LED Status Patterns
Observe the onboard status LED (`GPIO 2` / `LED_BUILTIN`):
- **Fast Blink (~5 Hz, 100ms on/off)**: ESP32 is connecting to Wi-Fi.
- **Slow Heartbeat (~1 Hz, 500ms on/off)**: Connected and actively receiving valid `MotionPacket` datagrams (age < 400ms).
- **Rapid Double-Blink**: Failsafe timeout triggered (>400ms elapsed since last valid packet).

### Step 6: Verify Diagnostic Reporting & Resilience
1. **Normal Reception**: Confirm Serial logs print steady valid packet updates with rolling rate and age:
   ```
   [UDP] seq=123  lin=45  ang=-10  flags=0x00  age=48ms  rate=20.1Hz
   ```
2. **Failsafe Timeout**: Terminate the gesture controller (`Ctrl+C`). Within ~400–1000ms, the ESP32 switches to the double-blink LED pattern and logs:
   ```
   [FAILSAFE] No signal from controller: packet age 420ms > 400ms timeout
   ```
   (Rate-limited to once per second).
3. **Corrupted Packet Rejection**: Send random datagrams to the ESP32 to verify rejection without rebooting or crashing:
   ```bash
   nc -u <esp32-ip> 5005 < /dev/urandom
   ```
   The serial monitor should report `[UDP ERROR] Invalid packet size` or `[UDP ERROR] Packet validation failed` and continue listening normally.
