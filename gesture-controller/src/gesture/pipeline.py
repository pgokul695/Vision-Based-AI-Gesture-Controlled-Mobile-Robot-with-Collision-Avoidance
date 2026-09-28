"""Pure gesture processing pipeline for vision-based robot control.

No camera, DOM, socket, or wall-clock access.
Time comes in as t_ms argument on every step(frame, t_ms) call.
"""

from dataclasses import dataclass, field
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Protocol flags (matching protocol/motion_packet.py and protocol/motion_packet.h)
FLAG_ESTOP: int = 1 << 0           # Bit 0: Emergency stop
FLAG_LOW_CONFIDENCE: int = 1 << 1  # Bit 1: Low confidence gesture detection
FLAG_FUN_TRICK: int = 1 << 2       # Bit 2: Fun trick activation (0x04)
FLAG_TURBO: int = 1 << 3           # Bit 3: Turbo speed mode (0x08)
FLAG_PRECISION: int = 1 << 4       # Bit 4: Precision speed mode (0x10)

LANDMARK_WRIST: int = 0
LANDMARK_INDEX_MCP: int = 5
LANDMARK_MIDDLE_MCP: int = 9
LANDMARK_RING_MCP: int = 13
LANDMARK_PINKY_MCP: int = 17


class OneEuroFilter:
    """Adaptive low-pass filter (Casiez et al., 2012)."""

    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.01, d_cutoff: float = 1.0) -> None:
        self.min_cutoff = float(min_cutoff)
        self.beta = float(beta)
        self.d_cutoff = float(d_cutoff)
        self.x_prev: Optional[float] = None
        self.dx_hat: float = 0.0
        self.last_t_ms: Optional[float] = None

    def reset(self) -> None:
        self.x_prev = None
        self.dx_hat = 0.0
        self.last_t_ms = None

    @staticmethod
    def _smoothing_factor(dt: float, cutoff: float) -> float:
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def filter(self, x: float, t_ms: float) -> float:
        if self.last_t_ms is None or self.x_prev is None:
            self.x_prev = float(x)
            self.dx_hat = 0.0
            self.last_t_ms = float(t_ms)
            return float(x)

        dt = (t_ms - self.last_t_ms) / 1000.0
        self.last_t_ms = float(t_ms)

        if dt <= 0.0:
            return self.x_prev
        # Clamp dt to prevent derivative spikes on resume
        if dt > 1.0:
            self.x_prev = float(x)
            self.dx_hat = 0.0
            return float(x)

        # Estimate derivative and filter it
        dx = (x - self.x_prev) / dt
        alpha_d = self._smoothing_factor(dt, self.d_cutoff)
        self.dx_hat = alpha_d * dx + (1.0 - alpha_d) * self.dx_hat

        # Calculate cutoff frequency and filter signal
        cutoff = self.min_cutoff + self.beta * abs(self.dx_hat)
        alpha = self._smoothing_factor(dt, cutoff)
        x_hat = alpha * x + (1.0 - alpha) * self.x_prev

        self.x_prev = x_hat
        return x_hat


class SlewLimiter:
    """Asymmetric slew rate limiter with sign-change passing through zero."""

    def __init__(
        self,
        accel_rate: float = 250.0,
        decel_rate: float = 800.0,
        steer_rate: float = 400.0,
        steer_decel_rate: float = 800.0,
    ) -> None:
        self.accel_rate = float(accel_rate)
        self.decel_rate = float(decel_rate)
        self.steer_rate = float(steer_rate)
        self.steer_decel_rate = float(steer_decel_rate)
        self.current_linear: float = 0.0
        self.current_angular: float = 0.0
        self.last_t_ms: Optional[float] = None

    def reset(self) -> None:
        self.current_linear = 0.0
        self.current_angular = 0.0
        self.last_t_ms = None

    @staticmethod
    def _step_rate(current: float, target: float, dt: float, accel_rate: float, decel_rate: float) -> float:
        if dt <= 0.0 or current == target:
            return float(target) if dt > 0.0 else current

        # Sign change: must decelerate through zero before accelerating
        if (current > 0.0 and target < 0.0) or (current < 0.0 and target > 0.0):
            decel_step = decel_rate * dt
            if abs(current) <= decel_step:
                time_to_zero = abs(current) / decel_rate
                remaining_dt = dt - time_to_zero
                accel_step = accel_rate * remaining_dt
                if target > 0.0:
                    return min(float(target), accel_step)
                else:
                    return max(float(target), -accel_step)
            else:
                return current - (decel_step if current > 0.0 else -decel_step)

        # Same direction or one is zero
        if abs(target) > abs(current):
            # Accelerating (magnitude increasing)
            step = accel_rate * dt
            diff = target - current
            if abs(diff) <= step:
                return float(target)
            return current + (step if diff > 0.0 else -step)
        else:
            # Decelerating (magnitude decreasing)
            step = decel_rate * dt
            diff = target - current
            if abs(diff) <= step:
                return float(target)
            return current + (step if diff > 0.0 else -step)

    def step(self, target_linear: float, target_angular: float, t_ms: float) -> Tuple[int, int]:
        if self.last_t_ms is None:
            self.last_t_ms = float(t_ms)
            self.current_linear = float(target_linear)
            self.current_angular = float(target_angular)
            return int(round(self.current_linear)), int(round(self.current_angular))

        dt = (t_ms - self.last_t_ms) / 1000.0
        self.last_t_ms = float(t_ms)

        # Clamp dt to prevent enormous leaps on frame stalls
        if dt > 0.2:
            dt = 0.2

        self.current_linear = self._step_rate(
            self.current_linear, target_linear, dt, self.accel_rate, self.decel_rate
        )
        self.current_angular = self._step_rate(
            self.current_angular, target_angular, dt, self.steer_rate, self.steer_decel_rate
        )

        lin_int = int(max(-100, min(100, round(self.current_linear))))
        ang_int = int(max(-100, min(100, round(self.current_angular))))
        return lin_int, ang_int


def apply_axis_shaping(
    val: float,
    full_scale: float,
    deadzone: float,
    sensitivity: float,
    expo: float,
) -> int:
    """Shared axis shaping per Task 4:
    1. Normalize using full_scale range and sensitivity multiplier.
    2. Deadzone with rescale: subtract deadzone and rescale remainder to [0, 1].
    3. Expo curve: y = sign(x) * (expo*|x|^3 + (1-expo)*|x|).
    4. Clamp to +-100.
    """
    if full_scale <= 0.0:
        return 0

    # 1. Normalize
    norm = (val / full_scale) * sensitivity
    sign = 1.0 if norm > 0.0 else (-1.0 if norm < 0.0 else 0.0)
    mag = abs(norm)

    # 2. Deadzone with rescale
    if mag <= deadzone:
        return 0
    if deadzone >= 1.0:
        return 0

    rescaled = (mag - deadzone) / (1.0 - deadzone)
    if rescaled > 1.0:
        rescaled = 1.0

    # 3. Expo curve
    y = sign * (expo * (rescaled ** 3) + (1.0 - expo) * rescaled)

    # 4. Scale to +-100 and clamp
    out = int(round(y * 100.0))
    return max(-100, min(100, out))


class GesturePipeline:
    """Pure gesture recognition and control pipeline."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        if config is None:
            config = self._load_default_config()
        self.config: Dict[str, Any] = config

        # Sub-configs
        self.control_mode = self.config.get("control_mode", "classic")
        self.sensitivity = float(self.config.get("sensitivity", 1.0))
        self.mirror_preview = bool(self.config.get("mirror_preview", True))
        self.smoothing_preset = self.config.get("smoothing_preset", "medium")

        self.sm_cfg = self.config.get("state_machine", {})
        self.map_cfg = self.config.get("mapping", {})
        self.ramp_cfg = self.config.get("ramping", {})

        # Filters
        preset_cfg = self.config.get("smoothing_presets", {}).get(
            self.smoothing_preset, {"min_cutoff": 1.0, "beta": 0.01, "d_cutoff": 1.0}
        )
        self.filter_x = OneEuroFilter(**preset_cfg)
        self.filter_y = OneEuroFilter(**preset_cfg)
        self.filter_tilt = OneEuroFilter(**preset_cfg)
        # Scale uses slower smoothing
        scale_preset = {"min_cutoff": 0.5, "beta": 0.002, "d_cutoff": 1.0}
        self.filter_scale = OneEuroFilter(**scale_preset)

        # Ramping
        self.limiter = SlewLimiter(
            accel_rate=self.ramp_cfg.get("accel_rate", 250.0),
            decel_rate=self.ramp_cfg.get("decel_rate", 800.0),
            steer_rate=self.ramp_cfg.get("steer_rate", 400.0),
            steer_decel_rate=self.ramp_cfg.get("steer_decel_rate", 800.0),
        )

        # State machine tracking
        self.state: str = "IDLE"  # IDLE, ENGAGING, DRIVING, GRACE, ESTOP
        self.estop_frames_count: int = 0
        self.engage_samples_x: List[float] = []
        self.engage_samples_y: List[float] = []
        self.engage_samples_tilt: List[float] = []
        self.grace_start_t_ms: float = 0.0
        self.last_held_linear: int = 0
        self.last_held_angular: int = 0

        # Anchor & Calibration
        self.anchor_x: Optional[float] = None
        self.anchor_y: Optional[float] = None
        self.neutral_tilt: float = 0.0

        # Latched modes
        self.turbo_latched: bool = False
        self.precision_latched: bool = False
        self.thumb_up_held_start_ms: Optional[float] = None
        self.thumb_up_toggled: bool = False
        self.victory_held_start_ms: Optional[float] = None
        self.victory_toggled: bool = False
        self.last_driving_t_ms: Optional[float] = None

        # Fun trick
        self.trick_held_start_ms: Optional[float] = None
        self.trick_fired_for_this_hold: bool = False
        self.last_trick_fire_t_ms: float = -999999.0

    @staticmethod
    def _load_default_config() -> Dict[str, Any]:
        candidates = [
            Path("gesture-config.json"),
            Path(__file__).resolve().parent.parent.parent.parent / "gesture-config.json",
            Path(__file__).resolve().parent.parent.parent / "webapp" / "gesture-config.json",
        ]
        for p in candidates:
            if p.is_file():
                try:
                    return json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    pass
        # Fallback inline defaults
        return {
            "control_mode": "classic",
            "mirror_preview": True,
            "sensitivity": 1.0,
            "smoothing_preset": "medium",
            "smoothing_presets": {
                "low": {"min_cutoff": 2.0, "beta": 0.05, "d_cutoff": 1.0},
                "medium": {"min_cutoff": 1.0, "beta": 0.01, "d_cutoff": 1.0},
                "high": {"min_cutoff": 0.5, "beta": 0.005, "d_cutoff": 1.0},
            },
            "state_machine": {
                "enter_conf": 0.7,
                "exit_conf": 0.4,
                "engage_frames": 4,
                "grace_ms": 150,
                "estop_frames": 2,
                "estop_conf": 0.5,
                "trick_hold_ms": 500,
                "trick_cooldown_ms": 3000,
                "mode_hold_ms": 400,
                "mode_timeout_ms": 2000,
            },
            "mapping": {
                "tilt_neutral": "calibrate_on_engage",
                "throttle_neutral": "anchor",
                "classic_tilt_full_scale": 40.0,
                "classic_tilt_deadzone": 0.10,
                "classic_throttle_full_scale": 1.0,
                "classic_throttle_deadzone": 0.15,
                "joystick_full_scale": 1.2,
                "joystick_deadzone": 0.15,
                "expo": 0.4,
                "min_hand_scale": 20.0,
            },
            "ramping": {
                "accel_rate": 250.0,
                "decel_rate": 800.0,
                "steer_rate": 400.0,
                "steer_decel_rate": 800.0,
            },
        }

    def set_control_mode(self, mode: str) -> None:
        if mode in ("classic", "joystick"):
            self.control_mode = mode
            self.config["control_mode"] = mode

    def set_sensitivity(self, sensitivity: float) -> None:
        self.sensitivity = max(0.1, min(3.0, float(sensitivity)))
        self.config["sensitivity"] = self.sensitivity

    def set_mirror_preview(self, mirror: bool) -> None:
        self.mirror_preview = bool(mirror)
        self.config["mirror_preview"] = self.mirror_preview

    def set_smoothing_preset(self, preset: str) -> None:
        if preset in self.config.get("smoothing_presets", {}):
            self.smoothing_preset = preset
            self.config["smoothing_preset"] = preset
            cfg = self.config["smoothing_presets"][preset]
            self.filter_x = OneEuroFilter(**cfg)
            self.filter_y = OneEuroFilter(**cfg)
            self.filter_tilt = OneEuroFilter(**cfg)

    def clear_latches(self) -> None:
        self.turbo_latched = False
        self.precision_latched = False

    def reset(self) -> None:
        self.state = "IDLE"
        self.estop_frames_count = 0
        self.engage_samples_x.clear()
        self.engage_samples_y.clear()
        self.engage_samples_tilt.clear()
        self.anchor_x = None
        self.anchor_y = None
        self.neutral_tilt = 0.0
        self.last_held_linear = 0
        self.last_held_angular = 0
        self.clear_latches()
        self.thumb_up_held_start_ms = None
        self.thumb_up_toggled = False
        self.victory_held_start_ms = None
        self.victory_toggled = False
        self.trick_held_start_ms = None
        self.trick_fired_for_this_hold = False
        self.filter_x.reset()
        self.filter_y.reset()
        self.filter_tilt.reset()
        self.filter_scale.reset()
        self.limiter.reset()

    def _extract_features(
        self, landmarks: List[Any], width: float, height: float
    ) -> Tuple[float, float, float, float]:
        """Convert normalized landmarks to user-space pixel coordinates and compute features."""
        # 1. User space conversion (flip x' = 1 - x) and aspect-ratio pixel scaling
        pts: List[Tuple[float, float]] = []
        for lm in landmarks:
            if isinstance(lm, (tuple, list)):
                raw_x, raw_y = lm[0], lm[1]
            elif hasattr(lm, "x") and hasattr(lm, "y"):
                raw_x, raw_y = lm.x, lm.y
            elif isinstance(lm, dict):
                raw_x, raw_y = lm["x"], lm["y"]
            else:
                raw_x, raw_y = 0.5, 0.5
            user_x = (1.0 - raw_x) * width
            user_y = raw_y * height
            pts.append((user_x, user_y))

        wrist = pts[LANDMARK_WRIST]
        k_indices = [LANDMARK_INDEX_MCP, LANDMARK_MIDDLE_MCP, LANDMARK_RING_MCP, LANDMARK_PINKY_MCP]
        kx = sum(pts[i][0] for i in k_indices) / 4.0
        ky = sum(pts[i][1] for i in k_indices) / 4.0

        # Hand axis from wrist to knuckle centroid
        dx = kx - wrist[0]
        dy = ky - wrist[1]  # In screen space, y is positive downwards
        # Vector pointing straight up has dx=0, dy < 0 (-dy > 0)
        # atan2(dx, -dy) yields 0 when vertical up, >0 tilted right, <0 tilted left
        raw_tilt_rad = math.atan2(dx, -dy)
        tilt_deg = math.degrees(raw_tilt_rad)
        # Clamp to [-90, 90]
        tilt_deg = max(-90.0, min(90.0, tilt_deg))

        # Hand scale: wrist to middle knuckle distance in pixel space
        middle_mcp = pts[LANDMARK_MIDDLE_MCP]
        scale_raw = math.hypot(middle_mcp[0] - wrist[0], middle_mcp[1] - wrist[1])
        min_scale = float(self.map_cfg.get("min_hand_scale", 20.0))
        scale = max(min_scale, scale_raw)

        return kx, ky, tilt_deg, scale

    def step(self, frame: Dict[str, Any], t_ms: float) -> Dict[str, Any]:
        """Process a frame at timestamp t_ms and return motion command + debug telemetry."""
        t_ms = float(t_ms)
        landmarks = frame.get("landmarks")
        gesture = frame.get("gesture")
        confidence = float(frame.get("confidence") or 0.0)
        width = float(frame.get("width") or 640.0)
        height = float(frame.get("height") or 480.0)

        # Thresholds
        enter_conf = float(self.sm_cfg.get("enter_conf", 0.7))
        exit_conf = float(self.sm_cfg.get("exit_conf", 0.4))
        engage_frames = int(self.sm_cfg.get("engage_frames", 4))
        grace_ms = float(self.sm_cfg.get("grace_ms", 150))
        estop_frames = int(self.sm_cfg.get("estop_frames", 2))
        estop_conf = float(self.sm_cfg.get("estop_conf", 0.5))
        trick_hold_ms = float(self.sm_cfg.get("trick_hold_ms", 500))
        trick_cooldown_ms = float(self.sm_cfg.get("trick_cooldown_ms", 3000))
        mode_hold_ms = float(self.sm_cfg.get("mode_hold_ms", 400))
        mode_timeout_ms = float(self.sm_cfg.get("mode_timeout_ms", 2000))

        has_landmarks = landmarks is not None and len(landmarks) >= 21

        # 1. Feature extraction & One Euro filtering
        feat_x, feat_y, feat_tilt, feat_scale = 0.0, 0.0, 0.0, 20.0
        smooth_x, smooth_y, smooth_tilt, smooth_scale = None, None, None, None
        if has_landmarks:
            feat_x, feat_y, feat_tilt, feat_scale = self._extract_features(landmarks, width, height)
            smooth_x = self.filter_x.filter(feat_x, t_ms)
            smooth_y = self.filter_y.filter(feat_y, t_ms)
            smooth_tilt = self.filter_tilt.filter(feat_tilt, t_ms)
            smooth_scale = self.filter_scale.filter(feat_scale, t_ms)

        # 2. Check Emergency Stop (Closed_Fist)
        is_fist = (gesture == "Closed_Fist") and (confidence >= estop_conf)
        if is_fist:
            self.estop_frames_count += 1
            if self.estop_frames_count >= estop_frames:
                self.state = "ESTOP"
        else:
            self.estop_frames_count = 0
            if self.state == "ESTOP":
                # Fist released -> return to IDLE, fresh engage required
                self.state = "IDLE"

        # 3. Handle Mode Latches & Fun Trick (only active when not in ESTOP)
        fun_trick_fire = False
        if self.state != "ESTOP":
            # Turbo (Thumb_Up)
            if gesture == "Thumb_Up" and confidence >= 0.5:
                if self.thumb_up_held_start_ms is None:
                    self.thumb_up_held_start_ms = t_ms
                elif (t_ms - self.thumb_up_held_start_ms) >= mode_hold_ms and not self.thumb_up_toggled:
                    self.turbo_latched = not self.turbo_latched
                    if self.turbo_latched:
                        self.precision_latched = False
                    self.thumb_up_toggled = True
            else:
                self.thumb_up_held_start_ms = None
                self.thumb_up_toggled = False

            # Precision (Victory)
            if gesture == "Victory" and confidence >= 0.5:
                if self.victory_held_start_ms is None:
                    self.victory_held_start_ms = t_ms
                elif (t_ms - self.victory_held_start_ms) >= mode_hold_ms and not self.victory_toggled:
                    self.precision_latched = not self.precision_latched
                    if self.precision_latched:
                        self.turbo_latched = False
                    self.victory_toggled = True
            else:
                self.victory_held_start_ms = None
                self.victory_toggled = False

            # Fun Trick (ILoveYou)
            if gesture == "ILoveYou" and confidence >= 0.5:
                if self.trick_held_start_ms is None:
                    self.trick_held_start_ms = t_ms
                elif (t_ms - self.trick_held_start_ms) >= trick_hold_ms and not self.trick_fired_for_this_hold:
                    if (t_ms - self.last_trick_fire_t_ms) >= trick_cooldown_ms:
                        fun_trick_fire = True
                        self.last_trick_fire_t_ms = t_ms
                        self.trick_fired_for_this_hold = True
            else:
                self.trick_held_start_ms = None
                self.trick_fired_for_this_hold = False

        # 4. State Machine Transitions
        is_open_palm = (gesture == "Open_Palm")
        pre_ramp_linear = 0
        pre_ramp_angular = 0

        if self.state == "ESTOP":
            # Instant zero output, bypasses ramping and smoothing
            self.limiter.reset()
            self.clear_latches()
            self.anchor_x = None
            self.anchor_y = None
            self.engage_samples_x.clear()
            self.engage_samples_y.clear()
            self.engage_samples_tilt.clear()
            flags = FLAG_ESTOP
            return {
                "linear": 0,
                "angular": 0,
                "flags": flags,
                "debug": {
                    "state": "ESTOP",
                    "anchor": None,
                    "smoothed_hand": [smooth_x, smooth_y] if smooth_x is not None else None,
                    "smoothed_tilt": smooth_tilt,
                    "smoothed_scale": smooth_scale,
                    "pre_ramp_linear": 0,
                    "pre_ramp_angular": 0,
                    "latched_mode": "NORMAL",
                    "control_mode": self.control_mode,
                    "neutral_tilt": self.neutral_tilt,
                    "neutral_y": self.anchor_y,
                },
            }

        # Check mode latch timeout when not in DRIVING
        if self.state == "DRIVING":
            self.last_driving_t_ms = t_ms
        else:
            if self.last_driving_t_ms is not None and (t_ms - self.last_driving_t_ms) > mode_timeout_ms:
                self.clear_latches()

        if self.state == "IDLE":
            if has_landmarks and is_open_palm and confidence >= enter_conf:
                self.state = "ENGAGING"
                self.engage_samples_x = [smooth_x]
                self.engage_samples_y = [smooth_y]
                self.engage_samples_tilt = [smooth_tilt]
                if engage_frames <= 1:
                    self._enter_driving(smooth_x, smooth_y, smooth_tilt)
            pre_ramp_linear = 0
            pre_ramp_angular = 0

        elif self.state == "ENGAGING":
            if has_landmarks and is_open_palm and confidence >= enter_conf:
                self.engage_samples_x.append(smooth_x)
                self.engage_samples_y.append(smooth_y)
                self.engage_samples_tilt.append(smooth_tilt)
                if len(self.engage_samples_x) >= engage_frames:
                    avg_x = sum(self.engage_samples_x) / len(self.engage_samples_x)
                    avg_y = sum(self.engage_samples_y) / len(self.engage_samples_y)
                    avg_tilt = sum(self.engage_samples_tilt) / len(self.engage_samples_tilt)
                    self._enter_driving(avg_x, avg_y, avg_tilt)
            else:
                # Interrupted engage -> back to IDLE
                self.state = "IDLE"
                self.engage_samples_x.clear()
                self.engage_samples_y.clear()
                self.engage_samples_tilt.clear()
            pre_ramp_linear = 0
            pre_ramp_angular = 0

        elif self.state == "DRIVING":
            if has_landmarks and is_open_palm and confidence >= exit_conf:
                # Compute continuous driving command
                pre_ramp_linear, pre_ramp_angular = self._compute_mapping(
                    smooth_x, smooth_y, smooth_tilt, smooth_scale, height
                )
                self.last_held_linear = pre_ramp_linear
                self.last_held_angular = pre_ramp_angular
            else:
                # Dropout detected -> enter GRACE
                self.state = "GRACE"
                self.grace_start_t_ms = t_ms
                pre_ramp_linear = self.last_held_linear
                pre_ramp_angular = self.last_held_angular

        elif self.state == "GRACE":
            if has_landmarks and is_open_palm and confidence >= exit_conf:
                # Recovered before timeout! Return to DRIVING
                self.state = "DRIVING"
                pre_ramp_linear, pre_ramp_angular = self._compute_mapping(
                    smooth_x, smooth_y, smooth_tilt, smooth_scale, height
                )
                self.last_held_linear = pre_ramp_linear
                self.last_held_angular = pre_ramp_angular
            elif (t_ms - self.grace_start_t_ms) < grace_ms:
                # Hold output target during grace window
                pre_ramp_linear = self.last_held_linear
                pre_ramp_angular = self.last_held_angular
            else:
                # Grace expired -> transition to IDLE, ramp target to 0
                self.state = "IDLE"
                self.anchor_x = None
                self.anchor_y = None
                self.last_held_linear = 0
                self.last_held_angular = 0
                pre_ramp_linear = 0
                pre_ramp_angular = 0

        # 5. Output Ramping (Slew Limiter)
        out_linear, out_angular = self.limiter.step(pre_ramp_linear, pre_ramp_angular, t_ms)

        # 6. Flag Assembly
        flags = 0
        if self.state in ("IDLE", "ENGAGING"):
            flags |= FLAG_LOW_CONFIDENCE
        elif self.state == "GRACE":
            flags |= FLAG_LOW_CONFIDENCE

        if self.turbo_latched:
            flags |= FLAG_TURBO
        elif self.precision_latched:
            flags |= FLAG_PRECISION

        if fun_trick_fire:
            flags |= FLAG_FUN_TRICK

        latched_label = "TURBO" if self.turbo_latched else ("PRECISION" if self.precision_latched else "NORMAL")

        return {
            "linear": out_linear,
            "angular": out_angular,
            "flags": flags,
            "debug": {
                "state": self.state,
                "anchor": [self.anchor_x, self.anchor_y] if self.anchor_x is not None else None,
                "smoothed_hand": [smooth_x, smooth_y] if smooth_x is not None else None,
                "smoothed_tilt": smooth_tilt,
                "smoothed_scale": smooth_scale,
                "pre_ramp_linear": pre_ramp_linear,
                "pre_ramp_angular": pre_ramp_angular,
                "latched_mode": latched_label,
                "control_mode": self.control_mode,
                "neutral_tilt": self.neutral_tilt,
                "neutral_y": self.anchor_y,
            },
        }

    def _enter_driving(self, anchor_x: float, anchor_y: float, neutral_tilt: float) -> None:
        self.state = "DRIVING"
        self.anchor_x = float(anchor_x)
        self.anchor_y = float(anchor_y)
        if self.map_cfg.get("tilt_neutral", "calibrate_on_engage") == "calibrate_on_engage":
            self.neutral_tilt = float(neutral_tilt)
        else:
            self.neutral_tilt = 0.0
        self.engage_samples_x.clear()
        self.engage_samples_y.clear()
        self.engage_samples_tilt.clear()

    def _compute_mapping(
        self,
        hand_x: float,
        hand_y: float,
        tilt_deg: float,
        hand_scale: float,
        frame_height: float,
    ) -> Tuple[int, int]:
        expo = float(self.map_cfg.get("expo", 0.4))
        scale = max(float(self.map_cfg.get("min_hand_scale", 20.0)), hand_scale)

        if self.control_mode == "joystick":
            # Joystick Mode
            full_scale = float(self.map_cfg.get("joystick_full_scale", 1.2))
            deadzone = float(self.map_cfg.get("joystick_deadzone", 0.15))

            anc_x = self.anchor_x if self.anchor_x is not None else hand_x
            anc_y = self.anchor_y if self.anchor_y is not None else hand_y

            # Deflection normalized by hand scale
            disp_x = (hand_x - anc_x) / scale
            # In screen coords y is positive downwards; up = forward = positive deflection
            disp_y = (anc_y - hand_y) / scale

            angular = apply_axis_shaping(disp_x, full_scale, deadzone, self.sensitivity, expo)
            linear = apply_axis_shaping(disp_y, full_scale, deadzone, self.sensitivity, expo)
            return linear, angular

        else:
            # Classic Mode (Improved)
            tilt_fs = float(self.map_cfg.get("classic_tilt_full_scale", 40.0))
            tilt_dz = float(self.map_cfg.get("classic_tilt_deadzone", 0.10))
            eff_tilt = tilt_deg - self.neutral_tilt
            angular = apply_axis_shaping(eff_tilt, tilt_fs, tilt_dz, self.sensitivity, expo)

            throttle_neutral_mode = self.map_cfg.get("throttle_neutral", "anchor")
            if throttle_neutral_mode == "anchor" and self.anchor_y is not None:
                neutral_y = self.anchor_y
            else:
                neutral_y = 0.5 * frame_height

            disp_y = (neutral_y - hand_y) / scale
            throttle_fs = float(self.map_cfg.get("classic_throttle_full_scale", 1.0))
            throttle_dz = float(self.map_cfg.get("classic_throttle_deadzone", 0.15))

            linear = apply_axis_shaping(disp_y, throttle_fs, throttle_dz, self.sensitivity, expo)
            return linear, angular
