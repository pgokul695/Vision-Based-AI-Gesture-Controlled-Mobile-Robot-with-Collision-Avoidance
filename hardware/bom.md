# Bill of Materials (BOM)

| Item # | Component | Model / Spec | Qty | Purpose | Notes |
|--------|-----------|--------------|-----|---------|-------|
| 1 | Microcontroller | ESP32-WROOM-32 Dev Module (30 or 38 pin) | 1 | Onboard controller, safety arbiter, and UDP receiver | Built-in 2.4GHz Wi-Fi |
| 2 | Motor Driver | L298N Dual H-Bridge or DRV8833 | 1 | Bi-directional DC motor control with PWM | Up to 2A per channel |
| 3 | Motors | 3V-9V TT Gearmotors (1:48 gear ratio) | 2 | Differential drive propulsion | Includes rubber wheels |
| 4 | Caster Wheel | Ball caster or omni-wheel | 1 | Passive balance support | Third point of contact |
| 5 | Ultrasonic Sensors | HC-SR04P or RCWL-1601 (3.3V compatible) | 3 | Front obstacle range detection | Angled array (-45°, 0°, +45°) |
| 6 | Digital IR Sensors | TCRT5000 or generic active-low IR proximity modules | 5 | Close-range & blindspot threshold detection | Front (2), Sides (2), Rear (1) |
| 7 | Power Source | USB-C Power Bank with PD (18W+ output) | 1 | System power supply | High energy density, no custom BMS required |
| 8 | PD Trigger Module | USB-C PD Decoy / Trigger Board (Configured to 9V) | 1 | Negotiates 9V rail from powerbank | Powers motors & ESP32 |
| 9 | Chassis Frame | 2WD Acrylic or 3D-printed chassis platform | 1 | Structural mount for hardware | Pre-drilled TT motor slots |
| 10 | Level Shifters / Resistors | 1kΩ & 2kΩ 1/4W resistors | 3 sets | 5V to 3.3V echo voltage dividers | Only needed if using 5V HC-SR04 |
| 11 | Prototyping Wiring | Breadboard / Protoboard & Dupont jumper wires | 1 set | Interconnects | Male-to-Female, Male-to-Male |
