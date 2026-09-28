/**
 * @file gesture-pipeline.js
 * @brief Pure gesture recognition and control pipeline in JavaScript (ES Module).
 *
 * Runs in both browser and Node.js without any DOM, camera, socket, or wall-clock dependencies.
 */

// Protocol flags matching protocol/motion_packet.h and motion_packet.py
export const FLAG_ESTOP = 1 << 0;          // Bit 0: Emergency stop
export const FLAG_LOW_CONFIDENCE = 1 << 1; // Bit 1: Low confidence gesture detection
export const FLAG_FUN_TRICK = 1 << 2;      // Bit 2: Fun trick activation (0x04)
export const FLAG_TURBO = 1 << 3;          // Bit 3: Turbo speed mode (0x08)
export const FLAG_PRECISION = 1 << 4;      // Bit 4: Precision speed mode (0x10)

export const LANDMARK_WRIST = 0;
export const LANDMARK_INDEX_MCP = 5;
export const LANDMARK_MIDDLE_MCP = 9;
export const LANDMARK_RING_MCP = 13;
export const LANDMARK_PINKY_MCP = 17;

export class OneEuroFilter {
    constructor(minCutoff = 1.0, beta = 0.01, dCutoff = 1.0) {
        this.minCutoff = Number(minCutoff);
        this.beta = Number(beta);
        this.dCutoff = Number(dCutoff);
        this.xPrev = null;
        this.dxHat = 0.0;
        this.lastTMs = null;
    }

    reset() {
        this.xPrev = null;
        this.dxHat = 0.0;
        this.lastTMs = null;
    }

    static _smoothingFactor(dt, cutoff) {
        const tau = 1.0 / (2.0 * Math.PI * cutoff);
        return 1.0 / (1.0 + tau / dt);
    }

    filter(x, tMs) {
        if (this.lastTMs === null || this.xPrev === null) {
            this.xPrev = Number(x);
            this.dxHat = 0.0;
            this.lastTMs = Number(tMs);
            return Number(x);
        }

        const dt = (tMs - this.lastTMs) / 1000.0;
        this.lastTMs = Number(tMs);

        if (dt <= 0.0) {
            return this.xPrev;
        }
        if (dt > 1.0) {
            this.xPrev = Number(x);
            this.dxHat = 0.0;
            return Number(x);
        }

        const dx = (x - this.xPrev) / dt;
        const alphaD = OneEuroFilter._smoothingFactor(dt, this.dCutoff);
        this.dxHat = alphaD * dx + (1.0 - alphaD) * this.dxHat;

        const cutoff = this.minCutoff + this.beta * Math.abs(this.dxHat);
        const alpha = OneEuroFilter._smoothingFactor(dt, cutoff);
        const xHat = alpha * x + (1.0 - alpha) * this.xPrev;

        this.xPrev = xHat;
        return xHat;
    }
}

export class SlewLimiter {
    constructor(accelRate = 250.0, decelRate = 800.0, steerRate = 400.0, steerDecelRate = 800.0) {
        this.accelRate = Number(accelRate);
        this.decelRate = Number(decelRate);
        this.steerRate = Number(steerRate);
        this.steerDecelRate = Number(steerDecelRate);
        this.currentLinear = 0.0;
        this.currentAngular = 0.0;
        this.lastTMs = null;
    }

    reset() {
        this.currentLinear = 0.0;
        this.currentAngular = 0.0;
        this.lastTMs = null;
    }

    static _stepRate(current, target, dt, accelRate, decelRate) {
        if (dt <= 0.0 || current === target) {
            return dt > 0.0 ? Number(target) : current;
        }

        // Sign change: must decelerate through zero before accelerating
        if ((current > 0.0 && target < 0.0) || (current < 0.0 && target > 0.0)) {
            const decelStep = decelRate * dt;
            if (Math.abs(current) <= decelStep) {
                const timeToZero = Math.abs(current) / decelRate;
                const remainingDt = dt - timeToZero;
                const accelStep = accelRate * remainingDt;
                if (target > 0.0) {
                    return Math.min(Number(target), accelStep);
                } else {
                    return Math.max(Number(target), -accelStep);
                }
            } else {
                return current - (current > 0.0 ? decelStep : -decelStep);
            }
        }

        // Same direction or one is zero
        if (Math.abs(target) > Math.abs(current)) {
            // Accelerating
            const step = accelRate * dt;
            const diff = target - current;
            if (Math.abs(diff) <= step) {
                return Number(target);
            }
            return current + (diff > 0.0 ? step : -step);
        } else {
            // Decelerating
            const step = decelRate * dt;
            const diff = target - current;
            if (Math.abs(diff) <= step) {
                return Number(target);
            }
            return current + (diff > 0.0 ? step : -step);
        }
    }

    step(targetLinear, targetAngular, tMs) {
        if (this.lastTMs === null) {
            this.lastTMs = Number(tMs);
            this.currentLinear = Number(targetLinear);
            this.currentAngular = Number(targetAngular);
            return [
                Math.max(-100, Math.min(100, Math.round(this.currentLinear) || 0)),
                Math.max(-100, Math.min(100, Math.round(this.currentAngular) || 0))
            ];
        }

        let dt = (tMs - this.lastTMs) / 1000.0;
        this.lastTMs = Number(tMs);

        if (dt > 0.2) {
            dt = 0.2;
        }

        this.currentLinear = SlewLimiter._stepRate(
            this.currentLinear, targetLinear, dt, this.accelRate, this.decelRate
        );
        this.currentAngular = SlewLimiter._stepRate(
            this.currentAngular, targetAngular, dt, this.steerRate, this.steerDecelRate
        );

        const linInt = Math.max(-100, Math.min(100, Math.round(this.currentLinear) || 0));
        const angInt = Math.max(-100, Math.min(100, Math.round(this.currentAngular) || 0));
        return [linInt, angInt];
    }
}

export function applyAxisShaping(val, fullScale, deadzone, sensitivity, expo) {
    if (fullScale <= 0.0) return 0;

    // 1. Normalize
    const norm = (val / fullScale) * sensitivity;
    const sign = norm > 0.0 ? 1.0 : (norm < 0.0 ? -1.0 : 0.0);
    const mag = Math.abs(norm);

    // 2. Deadzone with rescale
    if (mag <= deadzone || deadzone >= 1.0) return 0;

    let rescaled = (mag - deadzone) / (1.0 - deadzone);
    if (rescaled > 1.0) rescaled = 1.0;

    // 3. Expo curve
    const y = sign * (expo * Math.pow(rescaled, 3) + (1.0 - expo) * rescaled);

    // 4. Scale to +-100 and clamp
    const out = Math.round(y * 100.0) || 0;
    return Math.max(-100, min(100, out));

    function min(a, b) {
        return Math.min(a, b);
    }
}

export class GesturePipeline {
    constructor(config = null) {
        this.config = config || GesturePipeline.getDefaultConfig();

        this.controlMode = this.config.control_mode || 'classic';
        this.sensitivity = Number(this.config.sensitivity !== undefined ? this.config.sensitivity : 1.0);
        this.mirrorPreview = this.config.mirror_preview !== undefined ? Boolean(this.config.mirror_preview) : true;
        this.smoothingPreset = this.config.smoothing_preset || 'medium';

        this.smCfg = this.config.state_machine || {};
        this.mapCfg = this.config.mapping || {};
        this.rampCfg = this.config.ramping || {};

        // Filters
        const presets = this.config.smoothing_presets || {};
        const presetCfg = presets[this.smoothingPreset] || { min_cutoff: 1.0, beta: 0.01, d_cutoff: 1.0 };
        this.filterX = new OneEuroFilter(presetCfg.min_cutoff, presetCfg.beta, presetCfg.d_cutoff);
        this.filterY = new OneEuroFilter(presetCfg.min_cutoff, presetCfg.beta, presetCfg.d_cutoff);
        this.filterTilt = new OneEuroFilter(presetCfg.min_cutoff, presetCfg.beta, presetCfg.d_cutoff);
        this.filterScale = new OneEuroFilter(0.5, 0.002, 1.0);

        // Limiter
        this.limiter = new SlewLimiter(
            this.rampCfg.accel_rate !== undefined ? this.rampCfg.accel_rate : 250.0,
            this.rampCfg.decel_rate !== undefined ? this.rampCfg.decel_rate : 800.0,
            this.rampCfg.steer_rate !== undefined ? this.rampCfg.steer_rate : 400.0,
            this.rampCfg.steer_decel_rate !== undefined ? this.rampCfg.steer_decel_rate : 800.0
        );

        // State machine
        this.state = 'IDLE'; // IDLE, ENGAGING, DRIVING, GRACE, ESTOP
        this.estopFramesCount = 0;
        this.engageSamplesX = [];
        this.engageSamplesY = [];
        this.engageSamplesTilt = [];
        this.graceStartTMs = 0.0;
        this.lastHeldLinear = 0;
        this.lastHeldAngular = 0;

        // Anchor & Neutral
        this.anchorX = null;
        this.anchorY = null;
        this.neutralTilt = 0.0;

        // Latched modes
        this.turboLatched = false;
        this.precisionLatched = false;
        this.thumbUpHeldStartMs = null;
        this.thumbUpToggled = false;
        this.victoryHeldStartMs = null;
        this.victoryToggled = false;
        this.lastDrivingTMs = null;

        // Fun trick
        this.trickHeldStartMs = null;
        this.trickFiredForThisHold = false;
        this.lastTrickFireTMs = -999999.0;
    }

    static getDefaultConfig() {
        return {
            control_mode: 'classic',
            mirror_preview: true,
            sensitivity: 1.0,
            smoothing_preset: 'medium',
            smoothing_presets: {
                low: { min_cutoff: 2.0, beta: 0.05, d_cutoff: 1.0 },
                medium: { min_cutoff: 1.0, beta: 0.01, d_cutoff: 1.0 },
                high: { min_cutoff: 0.5, beta: 0.005, d_cutoff: 1.0 }
            },
            state_machine: {
                enter_conf: 0.7,
                exit_conf: 0.4,
                engage_frames: 4,
                grace_ms: 150,
                estop_frames: 2,
                estop_conf: 0.5,
                trick_hold_ms: 500,
                trick_cooldown_ms: 3000,
                mode_hold_ms: 400,
                mode_timeout_ms: 2000
            },
            mapping: {
                tilt_neutral: 'calibrate_on_engage',
                throttle_neutral: 'anchor',
                classic_tilt_full_scale: 40.0,
                classic_tilt_deadzone: 0.10,
                classic_throttle_full_scale: 1.0,
                classic_throttle_deadzone: 0.15,
                joystick_full_scale: 1.2,
                joystick_deadzone: 0.15,
                expo: 0.4,
                min_hand_scale: 20.0
            },
            ramping: {
                accel_rate: 250.0,
                decel_rate: 800.0,
                steer_rate: 400.0,
                steer_decel_rate: 800.0
            }
        };
    }

    setControlMode(mode) {
        if (mode === 'classic' || mode === 'joystick') {
            this.controlMode = mode;
            this.config.control_mode = mode;
        }
    }

    setSensitivity(s) {
        this.sensitivity = Math.max(0.1, Math.min(3.0, Number(s)));
        this.config.sensitivity = this.sensitivity;
    }

    setMirrorPreview(mirror) {
        this.mirrorPreview = Boolean(mirror);
        this.config.mirror_preview = this.mirrorPreview;
    }

    setSmoothingPreset(preset) {
        const presets = this.config.smoothing_presets || {};
        if (presets[preset]) {
            this.smoothingPreset = preset;
            this.config.smoothing_preset = preset;
            const cfg = presets[preset];
            this.filterX = new OneEuroFilter(cfg.min_cutoff, cfg.beta, cfg.d_cutoff);
            this.filterY = new OneEuroFilter(cfg.min_cutoff, cfg.beta, cfg.d_cutoff);
            this.filterTilt = new OneEuroFilter(cfg.min_cutoff, cfg.beta, cfg.d_cutoff);
        }
    }

    clearLatches() {
        this.turboLatched = false;
        this.precisionLatched = false;
    }

    reset() {
        this.state = 'IDLE';
        this.estopFramesCount = 0;
        this.engageSamplesX = [];
        this.engageSamplesY = [];
        this.engageSamplesTilt = [];
        this.anchorX = null;
        this.anchorY = null;
        this.neutralTilt = 0.0;
        this.lastHeldLinear = 0;
        this.lastHeldAngular = 0;
        this.clearLatches();
        this.thumbUpHeldStartMs = null;
        this.thumbUpToggled = false;
        this.victoryHeldStartMs = null;
        this.victoryToggled = false;
        this.trickHeldStartMs = null;
        this.trickFiredForThisHold = false;
        this.filterX.reset();
        this.filterY.reset();
        this.filterTilt.reset();
        this.filterScale.reset();
        this.limiter.reset();
    }

    _extractFeatures(landmarks, width, height) {
        const pts = [];
        for (let i = 0; i < landmarks.length; i++) {
            const lm = landmarks[i];
            let rawX = 0.5, rawY = 0.5;
            if (Array.isArray(lm)) {
                rawX = lm[0];
                rawY = lm[1];
            } else if (lm && lm.x !== undefined && lm.y !== undefined) {
                rawX = lm.x;
                rawY = lm.y;
            }
            // User space conversion: flip x' = 1 - x
            const userX = (1.0 - rawX) * width;
            const userY = rawY * height;
            pts.push({ x: userX, y: userY });
        }

        const wrist = pts[LANDMARK_WRIST];
        const kIndices = [LANDMARK_INDEX_MCP, LANDMARK_MIDDLE_MCP, LANDMARK_RING_MCP, LANDMARK_PINKY_MCP];
        let kxSum = 0.0, kySum = 0.0;
        for (const idx of kIndices) {
            kxSum += pts[idx].x;
            kySum += pts[idx].y;
        }
        const kx = kxSum / 4.0;
        const ky = kySum / 4.0;

        // Hand axis vector from wrist to knuckle centroid
        const dx = kx - wrist.x;
        const dy = ky - wrist.y;
        // In screen space y is downwards; straight up has dx=0, dy < 0 (-dy > 0)
        const rawTiltRad = Math.atan2(dx, -dy);
        let tiltDeg = rawTiltRad * (180.0 / Math.PI);
        tiltDeg = Math.max(-90.0, Math.min(90.0, tiltDeg));

        // Scale: wrist to middle knuckle distance in pixel space
        const middleMcp = pts[LANDMARK_MIDDLE_MCP];
        const scaleRaw = Math.hypot(middleMcp.x - wrist.x, middleMcp.y - wrist.y);
        const minScale = Number(this.mapCfg.min_hand_scale !== undefined ? this.mapCfg.min_hand_scale : 20.0);
        const scale = Math.max(minScale, scaleRaw);

        return [kx, ky, tiltDeg, scale];
    }

    step(frame, tMs) {
        tMs = Number(tMs);
        const landmarks = frame.landmarks;
        const gesture = frame.gesture;
        const confidence = Number(frame.confidence || 0.0);
        const width = Number(frame.width || 640.0);
        const height = Number(frame.height || 480.0);

        const enterConf = Number(this.smCfg.enter_conf !== undefined ? this.smCfg.enter_conf : 0.7);
        const exitConf = Number(this.smCfg.exit_conf !== undefined ? this.smCfg.exit_conf : 0.4);
        const engageFrames = Number(this.smCfg.engage_frames !== undefined ? this.smCfg.engage_frames : 4);
        const graceMs = Number(this.smCfg.grace_ms !== undefined ? this.smCfg.grace_ms : 150);
        const estopFrames = Number(this.smCfg.estop_frames !== undefined ? this.smCfg.estop_frames : 2);
        const estopConf = Number(this.smCfg.estop_conf !== undefined ? this.smCfg.estop_conf : 0.5);
        const trickHoldMs = Number(this.smCfg.trick_hold_ms !== undefined ? this.smCfg.trick_hold_ms : 500);
        const trickCooldownMs = Number(this.smCfg.trick_cooldown_ms !== undefined ? this.smCfg.trick_cooldown_ms : 3000);
        const modeHoldMs = Number(this.smCfg.mode_hold_ms !== undefined ? this.smCfg.mode_hold_ms : 400);
        const modeTimeoutMs = Number(this.smCfg.mode_timeout_ms !== undefined ? this.smCfg.mode_timeout_ms : 2000);

        const hasLandmarks = landmarks && Array.isArray(landmarks) && landmarks.length >= 21;

        // 1. Feature extraction & One Euro filtering
        let featX = 0.0, featY = 0.0, featTilt = 0.0, featScale = 20.0;
        let smoothX = null, smoothY = null, smoothTilt = null, smoothScale = null;
        if (hasLandmarks) {
            [featX, featY, featTilt, featScale] = this._extractFeatures(landmarks, width, height);
            smoothX = this.filterX.filter(featX, tMs);
            smoothY = this.filterY.filter(featY, tMs);
            smoothTilt = this.filterTilt.filter(featTilt, tMs);
            smoothScale = this.filterScale.filter(featScale, tMs);
        }

        // 2. Emergency Stop check (Closed_Fist)
        const isFist = (gesture === 'Closed_Fist') && (confidence >= estopConf);
        if (isFist) {
            this.estopFramesCount++;
            if (this.estopFramesCount >= estopFrames) {
                this.state = 'ESTOP';
            }
        } else {
            this.estopFramesCount = 0;
            if (this.state === 'ESTOP') {
                this.state = 'IDLE';
            }
        }

        // 3. Handle Mode Latches & Fun Trick (when not in ESTOP)
        let funTrickFire = false;
        if (this.state !== 'ESTOP') {
            // Turbo (Thumb_Up)
            if (gesture === 'Thumb_Up' && confidence >= 0.5) {
                if (this.thumbUpHeldStartMs === null) {
                    this.thumbUpHeldStartMs = tMs;
                } else if ((tMs - this.thumbUpHeldStartMs) >= modeHoldMs && !this.thumbUpToggled) {
                    this.turboLatched = !this.turboLatched;
                    if (this.turboLatched) {
                        this.precisionLatched = false;
                    }
                    this.thumbUpToggled = true;
                }
            } else {
                this.thumbUpHeldStartMs = null;
                this.thumbUpToggled = false;
            }

            // Precision (Victory)
            if (gesture === 'Victory' && confidence >= 0.5) {
                if (this.victoryHeldStartMs === null) {
                    this.victoryHeldStartMs = tMs;
                } else if ((tMs - this.victoryHeldStartMs) >= modeHoldMs && !this.victoryToggled) {
                    this.precisionLatched = !this.precisionLatched;
                    if (this.precisionLatched) {
                        this.turboLatched = false;
                    }
                    this.victoryToggled = true;
                }
            } else {
                this.victoryHeldStartMs = null;
                this.victoryToggled = false;
            }

            // Fun Trick (ILoveYou)
            if (gesture === 'ILoveYou' && confidence >= 0.5) {
                if (this.trickHeldStartMs === null) {
                    this.trickHeldStartMs = tMs;
                } else if ((tMs - this.trickHeldStartMs) >= trickHoldMs && !this.trickFiredForThisHold) {
                    if ((tMs - this.lastTrickFireTMs) >= trickCooldownMs) {
                        funTrickFire = true;
                        this.lastTrickFireTMs = tMs;
                        this.trickFiredForThisHold = true;
                    }
                }
            } else {
                this.trickHeldStartMs = null;
                this.trickFiredForThisHold = false;
            }
        }

        // 4. State Machine Transitions
        const isOpenPalm = (gesture === 'Open_Palm');
        let preRampLinear = 0;
        let preRampAngular = 0;

        if (this.state === 'ESTOP') {
            this.limiter.reset();
            this.clearLatches();
            this.anchorX = null;
            this.anchorY = null;
            this.engageSamplesX = [];
            this.engageSamplesY = [];
            this.engageSamplesTilt = [];
            return {
                linear: 0,
                angular: 0,
                flags: FLAG_ESTOP,
                debug: {
                    state: 'ESTOP',
                    anchor: null,
                    smoothed_hand: smoothX !== null ? [smoothX, smoothY] : null,
                    smoothed_tilt: smoothTilt,
                    smoothed_scale: smoothScale,
                    pre_ramp_linear: 0,
                    pre_ramp_angular: 0,
                    latched_mode: 'NORMAL',
                    control_mode: this.controlMode,
                    neutral_tilt: this.neutralTilt,
                    neutral_y: this.anchorY
                }
            };
        }

        // Mode latch timeout outside DRIVING
        if (this.state === 'DRIVING') {
            this.lastDrivingTMs = tMs;
        } else {
            if (this.lastDrivingTMs !== null && (tMs - this.lastDrivingTMs) > modeTimeoutMs) {
                this.clearLatches();
            }
        }

        if (this.state === 'IDLE') {
            if (hasLandmarks && isOpenPalm && confidence >= enterConf) {
                this.state = 'ENGAGING';
                this.engageSamplesX = [smoothX];
                this.engageSamplesY = [smoothY];
                this.engageSamplesTilt = [smoothTilt];
                if (engageFrames <= 1) {
                    this._enterDriving(smoothX, smoothY, smoothTilt);
                }
            }
            preRampLinear = 0;
            preRampAngular = 0;
        } else if (this.state === 'ENGAGING') {
            if (hasLandmarks && isOpenPalm && confidence >= enterConf) {
                this.engageSamplesX.push(smoothX);
                this.engageSamplesY.push(smoothY);
                this.engageSamplesTilt.push(smoothTilt);
                if (this.engageSamplesX.length >= engageFrames) {
                    const avgX = this.engageSamplesX.reduce((a, b) => a + b, 0) / this.engageSamplesX.length;
                    const avgY = this.engageSamplesY.reduce((a, b) => a + b, 0) / this.engageSamplesY.length;
                    const avgTilt = this.engageSamplesTilt.reduce((a, b) => a + b, 0) / this.engageSamplesTilt.length;
                    this._enterDriving(avgX, avgY, avgTilt);
                }
            } else {
                this.state = 'IDLE';
                this.engageSamplesX = [];
                this.engageSamplesY = [];
                this.engageSamplesTilt = [];
            }
            preRampLinear = 0;
            preRampAngular = 0;
        } else if (this.state === 'DRIVING') {
            if (hasLandmarks && isOpenPalm && confidence >= exitConf) {
                const cmd = this._computeMapping(smoothX, smoothY, smoothTilt, smoothScale, height);
                preRampLinear = cmd[0];
                preRampAngular = cmd[1];
                this.lastHeldLinear = preRampLinear;
                this.lastHeldAngular = preRampAngular;
            } else {
                this.state = 'GRACE';
                this.graceStartTMs = tMs;
                preRampLinear = this.lastHeldLinear;
                preRampAngular = this.lastHeldAngular;
            }
        } else if (this.state === 'GRACE') {
            if (hasLandmarks && isOpenPalm && confidence >= exitConf) {
                this.state = 'DRIVING';
                const cmd = this._computeMapping(smoothX, smoothY, smoothTilt, smoothScale, height);
                preRampLinear = cmd[0];
                preRampAngular = cmd[1];
                this.lastHeldLinear = preRampLinear;
                this.lastHeldAngular = preRampAngular;
            } else if ((tMs - this.graceStartTMs) < graceMs) {
                preRampLinear = this.lastHeldLinear;
                preRampAngular = this.lastHeldAngular;
            } else {
                this.state = 'IDLE';
                this.anchorX = null;
                this.anchorY = null;
                this.lastHeldLinear = 0;
                this.lastHeldAngular = 0;
                preRampLinear = 0;
                preRampAngular = 0;
            }
        }

        // 5. Output Ramping (Slew Limiter)
        const [outLinear, outAngular] = this.limiter.step(preRampLinear, preRampAngular, tMs);

        // 6. Flags
        let flags = 0;
        if (this.state === 'IDLE' || this.state === 'ENGAGING' || this.state === 'GRACE') {
            flags |= FLAG_LOW_CONFIDENCE;
        }

        if (this.turboLatched) {
            flags |= FLAG_TURBO;
        } else if (this.precisionLatched) {
            flags |= FLAG_PRECISION;
        }

        if (funTrickFire) {
            flags |= FLAG_FUN_TRICK;
        }

        const latchedLabel = this.turboLatched ? 'TURBO' : (this.precisionLatched ? 'PRECISION' : 'NORMAL');

        return {
            linear: outLinear,
            angular: outAngular,
            flags: flags,
            debug: {
                state: this.state,
                anchor: this.anchorX !== null ? [this.anchorX, this.anchorY] : null,
                smoothed_hand: smoothX !== null ? [smoothX, smoothY] : null,
                smoothed_tilt: smoothTilt,
                smoothed_scale: smoothScale,
                pre_ramp_linear: preRampLinear,
                pre_ramp_angular: preRampAngular,
                latched_mode: latchedLabel,
                control_mode: this.controlMode,
                neutral_tilt: this.neutralTilt,
                neutral_y: this.anchorY
            }
        };
    }

    _enterDriving(anchorX, anchorY, neutralTilt) {
        this.state = 'DRIVING';
        this.anchorX = Number(anchorX);
        this.anchorY = Number(anchorY);
        const neutralMode = this.mapCfg.tilt_neutral || 'calibrate_on_engage';
        if (neutralMode === 'calibrate_on_engage') {
            this.neutralTilt = Number(neutralTilt);
        } else {
            this.neutralTilt = 0.0;
        }
        this.engageSamplesX = [];
        this.engageSamplesY = [];
        this.engageSamplesTilt = [];
    }

    _computeMapping(handX, handY, tiltDeg, handScale, frameHeight) {
        const expo = Number(this.mapCfg.expo !== undefined ? this.mapCfg.expo : 0.4);
        const minScale = Number(this.mapCfg.min_hand_scale !== undefined ? this.mapCfg.min_hand_scale : 20.0);
        const scale = Math.max(minScale, handScale);

        if (this.controlMode === 'joystick') {
            const fullScale = Number(this.mapCfg.joystick_full_scale !== undefined ? this.mapCfg.joystick_full_scale : 1.2);
            const deadzone = Number(this.mapCfg.joystick_deadzone !== undefined ? this.mapCfg.joystick_deadzone : 0.15);

            const ancX = this.anchorX !== null ? this.anchorX : handX;
            const ancY = this.anchorY !== null ? this.anchorY : handY;

            const dispX = (handX - ancX) / scale;
            const dispY = (ancY - handY) / scale;

            const angular = applyAxisShaping(dispX, fullScale, deadzone, this.sensitivity, expo);
            const linear = applyAxisShaping(dispY, fullScale, deadzone, this.sensitivity, expo);
            return [linear, angular];
        } else {
            const tiltFs = Number(this.mapCfg.classic_tilt_full_scale !== undefined ? this.mapCfg.classic_tilt_full_scale : 40.0);
            const tiltDz = Number(this.mapCfg.classic_tilt_deadzone !== undefined ? this.mapCfg.classic_tilt_deadzone : 0.10);
            const effTilt = tiltDeg - this.neutralTilt;
            const angular = applyAxisShaping(effTilt, tiltFs, tiltDz, this.sensitivity, expo);

            const throttleMode = this.mapCfg.throttle_neutral || 'anchor';
            const neutralY = (throttleMode === 'anchor' && this.anchorY !== null) ? this.anchorY : 0.5 * frameHeight;

            const dispY = (neutralY - handY) / scale;
            const throttleFs = Number(this.mapCfg.classic_throttle_full_scale !== undefined ? this.mapCfg.classic_throttle_full_scale : 1.0);
            const throttleDz = Number(this.mapCfg.classic_throttle_deadzone !== undefined ? this.mapCfg.classic_throttle_deadzone : 0.15);

            const linear = applyAxisShaping(dispY, throttleFs, throttleDz, this.sensitivity, expo);
            return [linear, angular];
        }
    }
}
