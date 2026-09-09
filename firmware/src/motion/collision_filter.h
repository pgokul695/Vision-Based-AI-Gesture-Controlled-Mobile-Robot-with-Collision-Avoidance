/**
 * @file collision_filter.h
 * @brief Safety arbiter filtering incoming motion commands against obstacle
 * sensors.
 *
 * Safety rules enforced:
 * 1. Failsafe Timeout: If elapsed time since last valid packet > 400ms ->
 * output (0, 0).
 * 2. E-Stop: If packet has FLAG_ESTOP bit set -> output (0, 0).
 * 3. Front Zone (US + IR):
 *    - Hard stop on front IR trigger (linear <= 0 allowed, but positive forward
 * linear is zeroed).
 *    - Proportional forward speed slowdown as ultrasonic distance decreases
 * below threshold.
 * 4. Side Zones (Mid-IR):
 *    - Binary gate: If left side IR triggered, prohibit left turn (angular < 0
 * zeroed).
 *    - Binary gate: If right side IR triggered, prohibit right turn (angular >
 * 0 zeroed).
 * 5. Rear Zone (Rear-IR):
 *    - Binary gate: If rear IR triggered, prohibit reverse (linear < 0 zeroed).
 */

#ifndef COLLISION_FILTER_H
#define COLLISION_FILTER_H

#include "motion_packet.h"
#include "sensors/ir.h" #Build Prompt : Gesture - Controlled Diff - Drive Robot — Repo Scaffold + Protocol
#include "sensors/ultrasonic.h"
#include <stdbool.h>
#include <stdint.h>

Use this prompt with an agentic coding
    tool(e.g.Claude Code) in an empty project directory to scaffold the
    repo and implement the shared communication protocol.

    -- -

    ##Project Summary

    A gesture
    - controlled differential - drive robot.A laptop runs hand
    - gesture detection and sends motion commands wirelessly over WiFi(UDP) to an ESP32,
which drives two DC motors through a motor driver and performs onboard
collision avoidance using ultrasonic + IR sensors — independent of what the
laptop commands.

- **Firmware target**: ESP32 (PlatformIO, C++)
- **Host controller**: Laptop (Python, OpenCV + MediaPipe for gesture
  detection)
- **Link**: WiFi, UDP, fixed-format binary packet (not JSON — latency matters)
- **Power**: USB PD trigger board + powerbank (no charging circuit needed)
- **No wheel encoders** — open-loop motor control only, v1.

## Task 1 — Scaffold the Directory Structure

Create the following structure, with placeholder files (not empty — each
should have a short header comment describing its purpose and a TODO for
its real content):

```
gesture-robot/
├── README.md
├── firmware/
│   ├── platformio.ini
│   ├── src/
│   │   ├── main.cpp
│   │   ├── network/
│   │   │   ├── udp_receiver.cpp
│   │   │   └── udp_receiver.h
│   │   ├── motion/
│   │   │   ├── motor_driver.cpp
│   │   │   ├── motor_driver.h
│   │   │   ├── collision_filter.cpp
│   │   │   └── collision_filter.h
│   │   └── sensors/
│   │       ├── ultrasonic.cpp
│   │       ├── ultrasonic.h
│   │       ├── ir.cpp
│   │       └── ir.h
│   └── test/
│       └── test_collision_filter.cpp
│
├── gesture-controller/
│   ├── pyproject.toml
│   ├── src/
│   │   ├── main.py
│   │   ├── gesture/
│   │   │   ├── __init__.py
│   │   │   └── hand_tracker.py
│   │   └── network/
│   │       ├── __init__.py
│   │       └── udp_sender.py
│   └── tests/
│       └── test_hand_tracker.py
│
├── protocol/
│   ├── motion_packet.h
│   └── motion_packet.py
│
├── hardware/
│   ├── wiring-diagram.md
│   ├── bom.md
│   ├── pinout.md
│   └── enclosure/
│
├── docs/
│   ├── architecture.md
│   ├── protocol-spec.md
│   └── setup.md
│
└── .github/
    └── workflows/
        └── build-check.yml
```

`platformio.ini` should target `esp32dev` with `framework = arduino`.
`pyproject.toml` should declare dependencies: `opencv-python`, `mediapipe`,
`numpy`. `.gitignore` at repo root should cover `.pio/`, `__pycache__/`,
`*.pyc`, `.venv/`, `build/`.

## Task 2 — Implement the Shared Protocol

Both `protocol/motion_packet.h` (C, used by firmware) and
`protocol/motion_packet.py` (Python, used by gesture-controller) must define
the SAME 10-byte packed binary layout. Add a comment at the top of EACH file
explicitly pointing to the other, so a future change to one is a visible
prompt to change the other.

Packet layout (little-endian, packed, no implicit padding):

| Field    | Type    | Size | Meaning                                              |
|----------|---------|------|-------------------------------------------------------|
| magic    | uint8   | 1    | Fixed value `0xA5` — sanity check on receipt          |
| version  | uint8   | 1    | Protocol version, starts at `1`                       |
| seq      | uint16  | 2    | Increments per packet — detects stale/duplicate/out-of-order |
| linear   | int8    | 1    | -100..100, forward/back speed %                       |
| angular  | int8    | 1    | -100..100, turn rate %                                |
| flags    | uint8   | 1    | bit0=estop, bit1=low_confidence_gesture, bits2-7=reserved |
| reserved | uint8[3]| 3    | Padding for future fields (gesture_id, mode, etc.)    |

Total: 10 bytes.

- `motion_packet.h`: define as `struct __attribute__((packed)) MotionPacket {
  ... }`,
  plus a helper to validate `magic`/`version` on receive.
- `motion_packet.py`: define pack/unpack functions using the `struct` module
  with format string `<BBHbbB3s` (or equivalent), with a `MotionPacket`
  dataclass and `to_bytes()` / `from_bytes()` methods mirroring the C struct
  field-for-field.
- Write `docs/protocol-spec.md` describing the layout, the versioning policy
  (bump `version` on any breaking layout change, add new fields into
  `reserved` for non-breaking additions), and the receiver's timeout policy:
  if no valid packet arrives within 400ms, the ESP32 must zero the command
  (fail-safe stop) regardless of the last received values.

## Task 3 — Stub the Sensor + Collision Layer (interfaces only, no full logic yet)

`sensors/ultrasonic.h` / `.cpp`: interface for a front sensor array of 3 units
(front-left ~45°, front-center, front-right ~45°), round-robin triggered
(never fire more than one simultaneously) to avoid ultrasonic cross-talk.
Expose a function returning distance-per-sensor plus a "reading age" so the
collision filter can tell if a reading is stale.

`sensors/ir.h` / `.cpp`: interface for 5 IR sensors — 2 front (low-mounted,
tight-range), 2 side (chassis midpoint, left/right), 1 rear-center. Each is a
simple digital threshold read, polled every loop iteration (no multiplexing
needed).

`motion/collision_filter.h` / `.cpp`: takes the incoming `MotionPacket` plus
current sensor state and returns a safe `(linear, angular)` pair:
- Front zone (US + IR): proportional slowdown as ultrasonic distance
  decreases, hard stop on front IR trigger, regardless of commanded linear
  value.
- Side/rear zones (IR only): binary gate — zero out the specific direction of
  motion (turn toward a blocked side, or reverse) if that zone's IR is
  triggered. No proportional scaling needed there.
- If the incoming packet is stale (no valid packet within 400ms) or has
  `estop` flag set, output is always `(0, 0)`.

Leave the actual sensor-reading and PWM-output implementation as clearly
marked `// TODO` stubs — the goal of this pass is clean interfaces and file
structure, not the full working firmware yet.

## Task 4 — README and architecture doc

`README.md`: project name, one-paragraph description, high-level
architecture (laptop gesture → UDP → ESP32 → collision-filtered motor
output), and a "getting started" pointer to `docs/setup.md`.

`docs/architecture.md`: the system diagram (can be ASCII/mermaid) showing
laptop, WiFi link, ESP32, sensors, and motors, plus a short explanation of
why collision avoidance is enforced locally on the ESP32 rather than trusted
to the remote commander.

---

Once scaffolded, do NOT implement the full gesture-detection or motor-PWM
logic yet — stop after the structure, protocol, and stubbed interfaces are in
place and confirm before continuing.

#ifdef __cplusplus
extern "C" {
#endif

#define PACKET_TIMEOUT_MS 400
#define US_SLOWDOWN_DIST_CM 40.0f
#define US_STOP_DIST_CM 15.0f
#define US_READING_MAX_AGE_MS 300

  /**
   * @brief Filtered and validated motion output safe to pass to motor drivers.
   */
  typedef struct {
    int8_t linear;       // Safe linear speed (-100..100)
    int8_t angular;      // Safe angular turn rate (-100..100)
    bool estop_active;   // True if stopped due to host E-Stop flag
    bool timeout_active; // True if stopped due to >400ms packet gap
    bool front_blocked;  // True if forward motion suppressed by front US or IR
    bool side_left_blocked;  // True if left turn suppressed by left IR
    bool side_right_blocked; // True if right turn suppressed by right IR
    bool rear_blocked;       // True if reversing suppressed by rear IR
  } SafeMotionOutput;

  /**
   * @brief Threshold parameters for collision avoidance tuning.
   */
  typedef struct {
    float us_slowdown_distance_cm; // Distance at which linear speed scaling
                                   // begins
    float us_stop_distance_cm; // Distance at which forward motion is completely
                               // halted
    uint32_t packet_timeout_ms; // Max allowable silence before failsafe stop
                                // (default 400ms)
    uint32_t max_sensor_age_ms; // Max allowable sensor reading age before
                                // considered invalid
  } CollisionFilterConfig;

  /**
   * @brief Initializes collision filter configuration with default safe values.
   * @param config Optional custom configuration (NULL for defaults).
   */
  void collision_filter_init(const CollisionFilterConfig *config);

  /**
   * @brief Filters raw commanded motion packet through onboard safety
   * arbitration.
   *
   * @param raw_cmd The received MotionPacket from host.
   * @param packet_age_ms Time in ms since raw_cmd was received.
   * @param us_data Current ultrasonic sensor array readings.
   * @param ir_data Current IR sensor readings.
   * @param current_time_ms System timestamp in ms.
   * @param out_motion Output structure containing safe velocities and
   * intervention flags.
   */
  void collision_filter_process(
      const MotionPacket *raw_cmd, uint32_t packet_age_ms,
      const UltrasonicArrayReadings *us_data, const IRReadings *ir_data,
      uint32_t current_time_ms, SafeMotionOutput *out_motion);

#ifdef __cplusplus
}
#endif

#endif // COLLISION_FILTER_H
