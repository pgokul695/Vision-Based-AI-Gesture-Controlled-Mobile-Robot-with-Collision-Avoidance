# Vision-Based AI Gesture-Controlled Mobile Robot with Collision Avoidance

An intelligent, safety-critical differential-drive mobile robot controlled via computer vision hand gestures with local, deterministic collision avoidance. A laptop tracks user hand gestures in real time using OpenCV and MediaPipe, translating them into normalized motion commands transmitted over low-latency binary UDP datagrams to an onboard ESP32 microcontroller. The ESP32 evaluates incoming commands against a local obstacle array (3 front ultrasonic sensors and 5 digital IR sensors), actively scaling back speeds or forcing emergency stops to guarantee physical safety regardless of network delays or host command state.

---

## High-Level Architecture

```
[ Laptop Webcam ] ──> [ OpenCV + MediaPipe ] ──> [ Hand Gesture Classifier ]
                                                              │
                                                        10-byte Binary
                                                        UDP Datagram
                                                              │
                                                              v
[ 3x Ultrasonic Sensors ] ──┐                       [ ESP32 Microcontroller ]
[ 5x Digital IR Sensors ]  ─┼─> [ Collision Filter ] <── [ UDP Receiver ]
                            │      (Local Arbiter)
                            │             │
                            │      Safe (V, Omega)
                            │             v
                            └───> [ Motor Driver ] ──> [ 2x DC TT Motors ]
```

---

## Key Features

- **Low-Latency Binary UDP Protocol**: Lightweight 10-byte packed binary format (no JSON serialization overhead) running at 20-50 Hz with sequence counters and emergency stop flags.
- **Independent Onboard Safety Enforcement**: Sensor readings and safety overrides execute directly on the ESP32 in a real-time control loop, ensuring collision prevention even during Wi-Fi drops or software stalls.
- **Fail-Safe Timeout**: Autonomous zero-speed halt triggered if no valid packet arrives within 400 ms.
- **Multi-Sensor Fusion**:
  - 3x Front Ultrasonic array (-45°, 0°, +45°) with round-robin pinging to prevent acoustic crosstalk.
  - 5x Digital IR sensors guarding front low obstacles, chassis flanks, and rear blindspots.
- **Modular Codebase**: Clean separation between host computer vision (`gesture-controller/`), firmware (`firmware/`), and shared protocol definitions (`protocol/`).

---

## Repository Structure

```
├── README.md                 # Project summary and overview
├── firmware/                 # PlatformIO ESP32 firmware project
│   ├── platformio.ini        # PlatformIO configuration (esp32dev, Arduino)
│   ├── src/                  # Firmware source code
│   │   ├── main.cpp          # Setup and control loop
│   │   ├── network/          # UDP receiver module
│   │   ├── motion/           # Collision filter & motor driver
│   │   └── sensors/          # Ultrasonic and IR drivers
│   └── test/                 # Firmware unit tests
├── gesture-controller/       # Python laptop gesture controller
│   ├── pyproject.toml        # Dependencies (OpenCV, MediaPipe, NumPy)
│   ├── src/                  # Controller source code
│   │   ├── main.py           # Capture & transmission loop
│   │   ├── gesture/          # Hand tracking pipeline
│   │   └── network/          # UDP transmission client
│   └── tests/                # Controller unit tests
├── protocol/                 # Shared binary packet definitions
│   ├── motion_packet.h       # C/C++ struct definition
│   └── motion_packet.py      # Python dataclass and serializer
├── hardware/                 # Hardware schematics, BOM, pinout, enclosure
└── docs/                     # Architecture, protocol, and setup documentation
```

---

## Getting Started

To configure your development environment, flash the ESP32, and run the gesture controller, follow the step-by-step instructions in [docs/setup.md](file:///home/gokul/Project/Vision-Based-AI-Gesture-Controlled-Mobile-Robot-with-Collision-Avoidance/docs/setup.md).

For the full system design and safety analysis, see [docs/architecture.md](file:///home/gokul/Project/Vision-Based-AI-Gesture-Controlled-Mobile-Robot-with-Collision-Avoidance/docs/architecture.md).

For binary packet details and byte layout, see [docs/protocol-spec.md](file:///home/gokul/Project/Vision-Based-AI-Gesture-Controlled-Mobile-Robot-with-Collision-Avoidance/docs/protocol-spec.md).
