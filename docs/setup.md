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
python3 src/main.py --ip 192.168.4.1 --port 8888 --camera 0
```
