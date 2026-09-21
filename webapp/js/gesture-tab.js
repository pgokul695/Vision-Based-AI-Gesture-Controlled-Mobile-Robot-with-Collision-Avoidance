/**
 * @file gesture-tab.js
 * @brief MediaPipe Tasks Vision GestureRecognizer tab with camera HUD and deadman switch.
 *
 * Implements continuous tilt/throttle mapping ported directly from
 * gesture-controller/src/gesture/motion_mapper.py.
 */

import {
    FLAG_ESTOP,
    FLAG_LOW_CONFIDENCE,
    FLAG_FUN_TRICK,
    FLAG_TURBO,
    FLAG_PRECISION
} from './protocol.js';

// Tuning constants matching motion_mapper.py
const MAX_TILT_DEG = 40.0;
const THROTTLE_DEADZONE = 0.06;
const THROTTLE_FULL_RANGE = 0.35;
const NEUTRAL_Y = 0.5;
const DEFAULT_MIN_CONFIDENCE = 0.60;

const LANDMARK_WRIST = 0;
const LANDMARK_INDEX_MCP = 5;
const LANDMARK_PINKY_MCP = 17;

export class GestureTab {
    constructor() {
        this.container = null;
        this.videoElement = null;
        this.canvasElement = null;
        this.canvasCtx = null;
        this.stream = null;
        this.animFrameId = null;

        this.gestureRecognizer = null;
        this.isInitializing = false;
        this.isReady = false;
        this.hasCameraError = false;

        // Command output state
        this.linear = 0;
        this.angular = 0;
        this.flags = FLAG_LOW_CONFIDENCE;

        // Current detection telemetry
        this.currentGesture = 'None';
        this.currentConfidence = 0;
        this.trickTriggered = false;
        this.lastTrickGesture = false;

        this._processVideoFrame = this._processVideoFrame.bind(this);
    }

    mount(container) {
        this.container = container;
        this.container.innerHTML = `
            <div class="gesture-control-panel">
                <div class="gesture-header">
                    <div class="gesture-status-bar font-mono">
                        <span>GESTURE: <strong id="gst-label">DETECTING...</strong></span>
                        <span>CONF: <strong id="gst-conf">00%</strong></span>
                        <span>OUT: <strong id="gst-out">L:+00 A:+00</strong></span>
                    </div>
                </div>

                <div class="gesture-viewport-container">
                    <div id="gesture-error-banner" class="gesture-error-banner hidden">
                        <div class="banner-icon">⚠️</div>
                        <div class="banner-content">
                            <h4 id="gst-err-title">Camera Access Restricted</h4>
                            <p id="gst-err-msg">
                                Camera access requires a Secure Context (HTTPS or localhost).
                                When serving directly from ESP32 plain HTTP (<code>http://...</code>), mobile browsers disable the webcam.
                            </p>
                            <p class="banner-footnote">
                                <strong>Workarounds:</strong>
                                <br>1. Traditional Nav, WASD, and Joystick tabs work 100% on plain HTTP.
                                <br>2. To test Gesture tab on phone/laptop, run a local HTTPS server or configure Chrome's <code>unsafely-treat-insecure-origin-as-secure</code> flag.
                            </p>
                        </div>
                    </div>

                    <div class="video-wrapper" id="video-wrapper">
                        <video id="gesture-video" playsinline muted autoplay></video>
                        <canvas id="gesture-canvas"></canvas>
                        <div class="camera-crosshairs">
                            <div class="crosshair-neutral-band">
                                <span>NEUTRAL THROTTLE ZONE</span>
                            </div>
                        </div>
                    </div>

                    <div id="gesture-loading" class="gesture-loading-overlay">
                        <div class="spinner"></div>
                        <p id="gesture-loading-text">Loading MediaPipe Gesture Model...</p>
                    </div>
                </div>

                <div class="gesture-legend">
                    <div class="legend-item"><span class="legend-key">✋ Open Palm</span>: Continuous Tilt & Throttle</div>
                    <div class="legend-item"><span class="legend-key">✊ Closed Fist</span>: Emergency Stop</div>
                    <div class="legend-item"><span class="legend-key">👍 Thumb Up</span>: Turbo Speed (1.3x)</div>
                    <div class="legend-item"><span class="legend-key">✌️ Victory</span>: Precision Mode (0.5x)</div>
                    <div class="legend-item"><span class="legend-key">🤟 I Love You</span>: 360° Spin Trick</div>
                </div>
            </div>
        `;

        this.videoElement = this.container.querySelector('#gesture-video');
        this.canvasElement = this.container.querySelector('#gesture-canvas');
        this.canvasCtx = this.canvasElement.getContext('2d');

        this._startPipeline();
    }

    async _startPipeline() {
        // Step 1: Verify Camera Support & Context
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            this._showError(
                'Camera API Unavailable',
                'Your browser or current connection mode does not support getUserMedia. Mobile browsers require HTTPS for camera access.'
            );
            return;
        }

        try {
            // Step 2: Initialize MediaPipe Tasks Vision
            await this._initGestureRecognizer();

            // Step 3: Start Camera Stream
            await this._startCamera();

            // Step 4: Hide Loading Overlay and Start Recognition Loop
            const loadingOverlay = this.container?.querySelector('#gesture-loading');
            if (loadingOverlay) loadingOverlay.classList.add('hidden');
            this.isReady = true;

            this._processVideoFrame();
        } catch (err) {
            console.warn('[GestureTab] Initialization fallback:', err);
            this._showError('Camera / Model Initialization Note', err.message || err.toString());
        }
    }

    async _initGestureRecognizer() {
        const loadingText = this.container?.querySelector('#gesture-loading-text');
        if (loadingText) loadingText.textContent = 'Loading MediaPipe Vision Library...';

        const MP_CDN = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.18';
        const { GestureRecognizer, FilesetResolver } = await import(MP_CDN);

        if (loadingText) loadingText.textContent = 'Initializing Vision WASM Engine...';
        const filesetResolver = await FilesetResolver.forVisionTasks(`${MP_CDN}/wasm`);

        if (loadingText) loadingText.textContent = 'Loading Gesture Recognition Model...';

        // Attempt local model first, fallback to CDN
        let modelAssetPath = '/models/gesture_recognizer.task';
        try {
            const checkResp = await fetch(modelAssetPath, { method: 'HEAD' });
            if (!checkResp.ok) {
                throw new Error('Local model not found');
            }
        } catch (_) {
            // Fallback to Google CDN model
            modelAssetPath = 'https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task';
        }

        this.gestureRecognizer = await GestureRecognizer.createFromOptions(filesetResolver, {
            baseOptions: {
                modelAssetPath: modelAssetPath,
                delegate: 'GPU'
            },
            runningMode: 'VIDEO',
            numHands: 1,
            minHandDetectionConfidence: 0.5,
            minHandPresenceConfidence: 0.5,
            minTrackingConfidence: 0.5
        });
    }

    async _startCamera() {
        const loadingText = this.container?.querySelector('#gesture-loading-text');
        if (loadingText) loadingText.textContent = 'Requesting Camera Access...';

        const constraints = {
            audio: false,
            video: {
                facingMode: 'user',
                width: { ideal: 640 },
                height: { ideal: 480 }
            }
        };

        this.stream = await navigator.mediaDevices.getUserMedia(constraints);
        this.videoElement.srcObject = this.stream;

        return new Promise((resolve) => {
            this.videoElement.onloadedmetadata = () => {
                this.videoElement.play();
                this._syncCanvasSize();
                resolve();
            };
        });
    }

    _syncCanvasSize() {
        if (!this.videoElement || !this.canvasElement) return;
        const width = this.videoElement.videoWidth || 640;
        const height = this.videoElement.videoHeight || 480;
        this.canvasElement.width = width;
        this.canvasElement.height = height;
    }

    _processVideoFrame() {
        if (!this.isReady || !this.videoElement || this.videoElement.paused || this.videoElement.ended) {
            this.animFrameId = requestAnimationFrame(this._processVideoFrame);
            return;
        }

        const nowInMs = performance.now();
        let results = null;

        try {
            if (this.videoElement.readyState >= 2 && this.gestureRecognizer) {
                results = this.gestureRecognizer.recognizeForVideo(this.videoElement, nowInMs);
            }
        } catch (err) {
            console.warn('[GestureTab] Recognition frame error:', err);
        }

        this._handleRecognitionResult(results);
        this._renderOverlay(results);

        this.animFrameId = requestAnimationFrame(this._processVideoFrame);
    }

    _handleRecognitionResult(results) {
        if (!results || !results.landmarks || results.landmarks.length === 0 || !results.gestures || results.gestures.length === 0) {
            this._setZeroState('No Hand', 0);
            return;
        }

        const landmarks = results.landmarks[0];
        const gestureCandidate = results.gestures[0][0];

        if (!gestureCandidate) {
            this._setZeroState('Unknown', 0);
            return;
        }

        const gestureName = gestureCandidate.categoryName;
        const score = gestureCandidate.score;
        this.currentGesture = gestureName;
        this.currentConfidence = Math.round(score * 100);

        // Fun trick rising edge detection
        const isTrickGesture = (gestureName === 'ILoveYou');
        if (isTrickGesture && !this.lastTrickGesture) {
            this.trickTriggered = true;
        }
        this.lastTrickGesture = isTrickGesture;

        // Hard Emergency Stop
        if (gestureName === 'Closed_Fist') {
            this.linear = 0;
            this.angular = 0;
            this.flags = FLAG_ESTOP;
            this._updateUI(this.linear, this.angular, 'E-STOP');
            return;
        }

        // Low confidence deadman stop
        if (score < DEFAULT_MIN_CONFIDENCE) {
            this.linear = 0;
            this.angular = 0;
            this.flags = FLAG_LOW_CONFIDENCE;
            this._updateUI(this.linear, this.angular, 'LOW CONF');
            return;
        }

        // Deadman switch: Active driving allowed on Open_Palm, Thumb_Up (Turbo), or Victory (Precision)
        const canDrive = ['Open_Palm', 'Thumb_Up', 'Victory'].includes(gestureName);
        if (!canDrive) {
            this.linear = 0;
            this.angular = 0;
            this.flags = 0;
            if (this.trickTriggered) {
                this.flags |= FLAG_FUN_TRICK;
                this.trickTriggered = false;
            }
            this._updateUI(this.linear, this.angular, 'HOLD / IDLE');
            return;
        }

        // --- Continuous Differential Drive Math (Ported from motion_mapper.py) ---
        const wrist = landmarks[LANDMARK_WRIST];
        const indexMcp = landmarks[LANDMARK_INDEX_MCP];
        const pinkyMcp = landmarks[LANDMARK_PINKY_MCP];

        // 1. Steering via Knuckle Line Tilt Angle
        // Note: Camera feed is mirrored visually, so right-tilt = positive angular
        const dx = pinkyMcp.x - indexMcp.x;
        const dy = pinkyMcp.y - indexMcp.y;
        let angleDeg = Math.atan2(dy, dx) * (180.0 / Math.PI);

        if (angleDeg > 90.0) angleDeg -= 180.0;
        else if (angleDeg < -90.0) angleDeg += 180.0;

        const clampedAngle = Math.max(-MAX_TILT_DEG, Math.min(MAX_TILT_DEG, angleDeg));
        let angular = Math.round((clampedAngle / MAX_TILT_DEG) * 100.0);
        angular = Math.max(-100, Math.min(100, angular));

        // 2. Linear Throttle via Wrist Vertical Height
        const wristY = wrist.y;
        const effectiveRange = THROTTLE_FULL_RANGE - THROTTLE_DEADZONE;
        let linear = 0;

        if (effectiveRange > 0) {
            if (wristY < (NEUTRAL_Y - THROTTLE_DEADZONE)) {
                // Hand raised above neutral -> Forward (y decreases upwards in video coords)
                const displacement = (NEUTRAL_Y - THROTTLE_DEADZONE) - wristY;
                const throttle = Math.min(1.0, displacement / effectiveRange);
                linear = Math.round(throttle * 100.0);
            } else if (wristY > (NEUTRAL_Y + THROTTLE_DEADZONE)) {
                // Hand lowered below neutral -> Reverse (y increases downwards)
                const displacement = wristY - (NEUTRAL_Y + THROTTLE_DEADZONE);
                const throttle = Math.min(1.0, displacement / effectiveRange);
                linear = -Math.round(throttle * 100.0);
            }
        }
        linear = Math.max(-100, Math.min(100, linear));

        let flags = 0;
        if (gestureName === 'Thumb_Up') {
            flags |= FLAG_TURBO;
        } else if (gestureName === 'Victory') {
            flags |= FLAG_PRECISION;
        }

        if (this.trickTriggered) {
            flags |= FLAG_FUN_TRICK;
            this.trickTriggered = false;
        }

        this.linear = linear;
        this.angular = angular;
        this.flags = flags;

        const modeTag = (flags & FLAG_TURBO) ? 'TURBO' : (flags & FLAG_PRECISION) ? 'PREC' : 'DRIVE';
        this._updateUI(this.linear, this.angular, modeTag);
    }

    _setZeroState(label, conf) {
        this.currentGesture = label;
        this.currentConfidence = conf;
        this.linear = 0;
        this.angular = 0;
        this.flags = FLAG_LOW_CONFIDENCE;
        this._updateUI(0, 0, 'DEADMAN STOP');
    }

    _updateUI(lin, ang, mode) {
        const labelEl = this.container?.querySelector('#gst-label');
        const confEl = this.container?.querySelector('#gst-conf');
        const outEl = this.container?.querySelector('#gst-out');

        if (labelEl) labelEl.textContent = `${this.currentGesture} (${mode})`;
        if (confEl) confEl.textContent = `${this.currentConfidence}%`;
        if (outEl) {
            const lStr = (lin >= 0 ? '+' : '') + lin.toString().padStart(3, '0');
            const aStr = (ang >= 0 ? '+' : '') + ang.toString().padStart(3, '0');
            outEl.textContent = `L:${lStr} A:${aStr}`;
        }
    }

    _renderOverlay(results) {
        if (!this.canvasCtx || !this.canvasElement) return;
        const ctx = this.canvasCtx;
        const w = this.canvasElement.width;
        const h = this.canvasElement.height;

        ctx.clearRect(0, 0, w, h);

        if (!results || !results.landmarks || results.landmarks.length === 0) {
            return;
        }

        const landmarks = results.landmarks[0];

        // Draw connections / skeleton
        ctx.strokeStyle = '#f59e0b'; // Amber accent
        ctx.lineWidth = 3;
        ctx.fillStyle = '#10b981';  // Green landmark dots

        // Simple skeleton connections
        const connections = [
            [0, 1], [1, 2], [2, 3], [3, 4],       // Thumb
            [0, 5], [5, 6], [6, 7], [7, 8],       // Index
            [5, 9], [9, 10], [10, 11], [11, 12],  // Middle
            [9, 13], [13, 14], [14, 15], [15, 16],// Ring
            [13, 17], [17, 18], [18, 19], [19, 20],// Pinky
            [0, 17]                               // Palm base
        ];

        ctx.beginPath();
        for (const [start, end] of connections) {
            const p1 = landmarks[start];
            const p2 = landmarks[end];
            ctx.moveTo(p1.x * w, p1.y * h);
            ctx.lineTo(p2.x * w, p2.y * h);
        }
        ctx.stroke();

        // Highlight Knuckle tilt line
        const pIndex = landmarks[LANDMARK_INDEX_MCP];
        const pPinky = landmarks[LANDMARK_PINKY_MCP];
        ctx.strokeStyle = '#38bdf8'; // Cyan tilt line
        ctx.lineWidth = 4;
        ctx.beginPath();
        ctx.moveTo(pIndex.x * w, pIndex.y * h);
        ctx.lineTo(pPinky.x * w, pPinky.y * h);
        ctx.stroke();

        // Draw landmarks
        for (let i = 0; i < landmarks.length; i++) {
            const p = landmarks[i];
            const px = p.x * w;
            const py = p.y * h;

            ctx.beginPath();
            ctx.arc(px, py, (i === 0 || i === 5 || i === 17) ? 6 : 4, 0, 2 * Math.PI);
            ctx.fill();
        }
    }

    _showError(title, message) {
        this.hasCameraError = true;
        const banner = this.container?.querySelector('#gesture-error-banner');
        const titleEl = this.container?.querySelector('#gst-err-title');
        const msgEl = this.container?.querySelector('#gst-err-msg');
        const loading = this.container?.querySelector('#gesture-loading');

        if (titleEl) titleEl.textContent = title;
        if (msgEl) msgEl.textContent = message;
        if (banner) banner.classList.remove('hidden');
        if (loading) loading.classList.add('hidden');
    }

    getCommand() {
        return {
            linear: this.linear,
            angular: this.angular,
            flags: this.flags
        };
    }

    reset() {
        this.linear = 0;
        this.angular = 0;
        this.flags = FLAG_LOW_CONFIDENCE;
        this.trickTriggered = false;
        this.lastTrickGesture = false;
        if (this.canvasCtx && this.canvasElement) {
            this.canvasCtx.clearRect(0, 0, this.canvasElement.width, this.canvasElement.height);
        }
    }

    destroy() {
        this.reset();
        this.isReady = false;

        if (this.animFrameId) {
            cancelAnimationFrame(this.animFrameId);
            this.animFrameId = null;
        }

        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }

        if (this.videoElement) {
            this.videoElement.srcObject = null;
        }
    }
}
