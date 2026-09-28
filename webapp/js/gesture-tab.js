/**
 * @file gesture-tab.js
 * @brief MediaPipe Tasks Vision GestureRecognizer tab with pure GesturePipeline,
 *        canvas HUD overlay, and client-side settings persistence.
 */

import {
    FLAG_ESTOP,
    FLAG_LOW_CONFIDENCE,
    FLAG_FUN_TRICK,
    FLAG_TURBO,
    FLAG_PRECISION,
    GesturePipeline
} from './gesture-pipeline.js';

export class GestureTab {
    constructor() {
        this.container = null;
        this.videoElement = null;
        this.canvasElement = null;
        this.canvasCtx = null;
        this.stream = null;
        this.animFrameId = null;
        this.videoCallbackId = null;

        this.gestureRecognizer = null;
        this.isReady = false;
        this.hasConfigError = false;

        this.config = null;
        this.pipeline = null;

        // Current settings (hydrated from config + localStorage)
        this.settings = {
            controlMode: 'classic',
            smoothingPreset: 'medium',
            sensitivity: 1.0,
            mirrorPreview: true,
            showDebug: false
        };

        // Command output state
        this.linear = 0;
        this.angular = 0;
        this.flags = FLAG_LOW_CONFIDENCE;
        this.lastStepResult = null;

        // FPS and latency telemetry
        this.fps = 0.0;
        this.latencyMs = 0.0;
        this.frameCount = 0;
        this.fpsStartTime = performance.now();

        this._processVideoFrame = this._processVideoFrame.bind(this);
    }

    mount(container) {
        this.container = container;
        this.container.innerHTML = `
            <div class="gesture-control-panel">
                <div class="gesture-header">
                    <div class="gesture-status-bar font-mono">
                        <span>STATE: <strong id="gst-state">IDLE</strong></span>
                        <span>GESTURE: <strong id="gst-label">DETECTING...</strong></span>
                        <span>MODE: <strong id="gst-mode">NORMAL</strong></span>
                        <span>OUT: <strong id="gst-out">L:+00 A:+00</strong></span>
                    </div>
                </div>

                <div class="gesture-viewport-container">
                    <div id="gesture-error-banner" class="gesture-error-banner hidden">
                        <div class="banner-icon">⚠️</div>
                        <div class="banner-content">
                            <h4 id="gst-err-title">Notice</h4>
                            <p id="gst-err-msg"></p>
                        </div>
                    </div>

                    <div class="video-wrapper" id="video-wrapper">
                        <video id="gesture-video" class="mirrored" playsinline muted autoplay></video>
                        <canvas id="gesture-canvas" class="mirrored"></canvas>
                        <div class="camera-crosshairs" id="camera-crosshairs">
                            <div class="crosshair-neutral-band" id="crosshair-band">
                                <span>NEUTRAL ZONE</span>
                            </div>
                        </div>
                    </div>

                    <div id="gesture-loading" class="gesture-loading-overlay">
                        <div class="spinner"></div>
                        <p id="gesture-loading-text">Loading Gesture Controller...</p>
                    </div>
                </div>

                <div class="gesture-legend">
                    <div class="legend-item"><span class="legend-key">✋ Open Palm</span>: Continuous Drive</div>
                    <div class="legend-item"><span class="legend-key">✊ Closed Fist</span>: Instant E-Stop</div>
                    <div class="legend-item"><span class="legend-key">👍 Thumb Up</span>: Latch Turbo</div>
                    <div class="legend-item"><span class="legend-key">✌️ Victory</span>: Latch Precision</div>
                    <div class="legend-item"><span class="legend-key">🤟 I Love You</span>: Spin Trick</div>
                </div>
            </div>
        `;

        this.videoElement = this.container.querySelector('#gesture-video');
        this.canvasElement = this.container.querySelector('#gesture-canvas');
        this.canvasCtx = this.canvasElement.getContext('2d');

        this._startPipeline();
    }

    async _startPipeline() {
        // Step 1: Load gesture-config.json
        const configLoaded = await this._loadConfig();
        if (!configLoaded) {
            return;
        }

        // Step 2: Initialize GesturePipeline with settings
        this._initPipelineWithSettings();

        // Step 3: Check camera access
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            this._showError(
                'Camera Access Restricted',
                'Camera API is unavailable. Modern mobile browsers require HTTPS or localhost for webcam access. If running over plain HTTP, use the Traditional Nav, WASD, or Joystick tabs.'
            );
            return;
        }

        try {
            // Step 4: Initialize MediaPipe Tasks Vision
            await this._initGestureRecognizer();

            // Step 5: Start camera
            await this._startCamera();

            // Step 6: Ready! Hide loading and start video frame loop
            const loadingOverlay = this.container?.querySelector('#gesture-loading');
            if (loadingOverlay) loadingOverlay.classList.add('hidden');
            this.isReady = true;

            this._scheduleNextFrame();
        } catch (err) {
            console.warn('[GestureTab] Initialization error:', err);
            this._showError('Model / Camera Initialization Note', err.message || err.toString());
        }
    }

    async _loadConfig() {
        const loadingText = this.container?.querySelector('#gesture-loading-text');
        if (loadingText) loadingText.textContent = 'Loading gesture configuration...';

        try {
            const resp = await fetch('gesture-config.json');
            if (!resp.ok) {
                throw new Error(`HTTP ${resp.status} ${resp.statusText}`);
            }
            this.config = await resp.json();
            return true;
        } catch (err) {
            console.error('[GestureTab] Failed to load gesture-config.json:', err);
            this._showError(
                'Gesture Config Error',
                `Failed to load gesture-config.json: ${err.message}. Other tabs remain functional.`
            );
            return false;
        }
    }

    _initPipelineWithSettings() {
        // Read persisted settings from localStorage with fallback
        this.loadSettings();

        this.pipeline = new GesturePipeline(this.config);
        this.pipeline.setControlMode(this.settings.controlMode);
        this.pipeline.setSensitivity(this.settings.sensitivity);
        this.pipeline.setSmoothingPreset(this.settings.smoothingPreset);
        this.pipeline.setMirrorPreview(this.settings.mirrorPreview);

        this._applyMirrorClass();
    }

    loadSettings() {
        // Fall back to config defaults
        if (this.config) {
            this.settings.controlMode = this.config.control_mode || 'classic';
            this.settings.smoothingPreset = this.config.smoothing_preset || 'medium';
            this.settings.sensitivity = Number(this.config.sensitivity !== undefined ? this.config.sensitivity : 1.0);
            this.settings.mirrorPreview = this.config.mirror_preview !== undefined ? Boolean(this.config.mirror_preview) : true;
        }

        try {
            const raw = localStorage.getItem('gesture_ergonomics_settings');
            if (raw) {
                const parsed = JSON.parse(raw);
                if (parsed.controlMode) this.settings.controlMode = parsed.controlMode;
                if (parsed.smoothingPreset) this.settings.smoothingPreset = parsed.smoothingPreset;
                if (parsed.sensitivity !== undefined) this.settings.sensitivity = Number(parsed.sensitivity);
                if (parsed.mirrorPreview !== undefined) this.settings.mirrorPreview = Boolean(parsed.mirrorPreview);
                if (parsed.showDebug !== undefined) this.settings.showDebug = Boolean(parsed.showDebug);
            }
        } catch (e) {
            console.warn('[GestureTab] Could not load localStorage settings:', e);
        }
    }

    saveSettings(newSettings) {
        Object.assign(this.settings, newSettings);
        try {
            localStorage.setItem('gesture_ergonomics_settings', JSON.stringify(this.settings));
        } catch (e) {
            console.warn('[GestureTab] Could not save settings to localStorage:', e);
        }

        if (this.pipeline) {
            this.pipeline.setControlMode(this.settings.controlMode);
            this.pipeline.setSensitivity(this.settings.sensitivity);
            this.pipeline.setSmoothingPreset(this.settings.smoothingPreset);
            this.pipeline.setMirrorPreview(this.settings.mirrorPreview);
        }

        this._applyMirrorClass();
    }

    _applyMirrorClass() {
        const mirror = this.settings.mirrorPreview;
        if (this.videoElement) {
            this.videoElement.className = mirror ? 'mirrored' : 'unmirrored';
        }
        if (this.canvasElement) {
            this.canvasElement.className = mirror ? 'mirrored' : 'unmirrored';
        }
    }

    async _initGestureRecognizer() {
        const loadingText = this.container?.querySelector('#gesture-loading-text');
        if (loadingText) loadingText.textContent = 'Loading MediaPipe Vision Library...';

        const MP_CDN = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14';
        const { GestureRecognizer, FilesetResolver } = await import(`${MP_CDN}/vision_bundle.mjs`);

        if (loadingText) loadingText.textContent = 'Initializing Vision WASM Engine...';
        const filesetResolver = await FilesetResolver.forVisionTasks(`${MP_CDN}/wasm`);

        if (loadingText) loadingText.textContent = 'Loading Gesture Recognition Model...';

        let modelAssetPath = 'models/gesture_recognizer.task';
        try {
            const checkResp = await fetch(modelAssetPath, { method: 'HEAD' });
            if (!checkResp.ok) throw new Error('Local model not found');
        } catch (_) {
            modelAssetPath = 'https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task';
        }

        const recognizerOptions = {
            runningMode: 'VIDEO',
            numHands: 1,
            minHandDetectionConfidence: 0.5,
            minHandPresenceConfidence: 0.5,
            minTrackingConfidence: 0.5
        };

        // Try GPU delegate first, fallback to CPU
        try {
            this.gestureRecognizer = await GestureRecognizer.createFromOptions(filesetResolver, {
                baseOptions: { modelAssetPath: modelAssetPath, delegate: 'GPU' },
                ...recognizerOptions
            });
        } catch (gpuErr) {
            console.warn('[GestureTab] GPU delegate failed, falling back to CPU:', gpuErr);
            this.gestureRecognizer = await GestureRecognizer.createFromOptions(filesetResolver, {
                baseOptions: { modelAssetPath: modelAssetPath, delegate: 'CPU' },
                ...recognizerOptions
            });
        }
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

    _scheduleNextFrame() {
        if (!this.isReady) return;

        if (this.videoElement && 'requestVideoFrameCallback' in this.videoElement) {
            this.videoCallbackId = this.videoElement.requestVideoFrameCallback((now, metadata) => {
                this._processVideoFrame(now, metadata);
            });
        } else {
            this.animFrameId = requestAnimationFrame((now) => {
                this._processVideoFrame(now);
            });
        }
    }

    _processVideoFrame(nowInMs, metadata = null) {
        if (!this.isReady || !this.videoElement || this.videoElement.paused || this.videoElement.ended) {
            this._scheduleNextFrame();
            return;
        }

        const frameStartTime = performance.now();
        let results = null;

        try {
            if (this.videoElement.readyState >= 2 && this.gestureRecognizer) {
                results = this.gestureRecognizer.recognizeForVideo(this.videoElement, frameStartTime);
            }
        } catch (err) {
            console.warn('[GestureTab] Recognition error:', err);
        }

        this.latencyMs = performance.now() - frameStartTime;

        // Calculate FPS
        this.frameCount++;
        const elapsed = performance.now() - this.fpsStartTime;
        if (elapsed >= 1000) {
            this.fps = (this.frameCount * 1000) / elapsed;
            this.frameCount = 0;
            this.fpsStartTime = performance.now();
        }

        // Construct frame input
        const width = this.videoElement.videoWidth || 640;
        const height = this.videoElement.videoHeight || 480;
        const firstHandLandmarks = results?.landmarks?.[0] || null;
        const firstGesture = results?.gestures?.[0]?.[0] || null;

        const frameInput = {
            landmarks: firstHandLandmarks,
            gesture: firstGesture ? firstGesture.categoryName : null,
            confidence: firstGesture ? firstGesture.score : 0.0,
            width: width,
            height: height
        };

        if (this.pipeline) {
            const stepResult = this.pipeline.step(frameInput, frameStartTime);
            this.linear = stepResult.linear;
            this.angular = stepResult.angular;
            this.flags = stepResult.flags;
            this.lastStepResult = stepResult;

            this._updateUI(stepResult, frameInput);
            this._renderOverlay(stepResult, results, width, height);
        }

        this._scheduleNextFrame();
    }

    _updateUI(stepResult, frameInput) {
        const stateEl = this.container?.querySelector('#gst-state');
        const labelEl = this.container?.querySelector('#gst-label');
        const modeEl = this.container?.querySelector('#gst-mode');
        const outEl = this.container?.querySelector('#gst-out');

        const debug = stepResult.debug;
        const state = debug.state;
        const latchedMode = debug.latched_mode;

        if (stateEl) {
            stateEl.textContent = state;
            const stateColors = {
                IDLE: 'var(--text-muted)',
                ENGAGING: 'var(--accent-amber)',
                DRIVING: 'var(--status-green)',
                GRACE: '#f97316',
                ESTOP: 'var(--status-red)'
            };
            stateEl.style.color = stateColors[state] || 'var(--text-primary)';
        }

        if (labelEl) {
            const gName = frameInput.gesture || 'None';
            const conf = Math.round(frameInput.confidence * 100);
            labelEl.textContent = `${gName} (${conf}%)`;
        }

        if (modeEl) {
            modeEl.textContent = latchedMode;
            if (latchedMode === 'TURBO') modeEl.style.color = 'var(--status-yellow)';
            else if (latchedMode === 'PRECISION') modeEl.style.color = 'var(--status-blue)';
            else modeEl.style.color = 'var(--text-muted)';
        }

        if (outEl) {
            const lStr = (this.linear >= 0 ? '+' : '') + this.linear.toString().padStart(3, '0');
            const aStr = (this.angular >= 0 ? '+' : '') + this.angular.toString().padStart(3, '0');
            outEl.textContent = `L:${lStr} A:${aStr}`;
        }
    }

    _renderOverlay(stepResult, results, width, height) {
        if (!this.canvasCtx || !this.canvasElement) return;
        const ctx = this.canvasCtx;

        ctx.clearRect(0, 0, width, height);

        const debug = stepResult.debug;
        const state = debug.state;
        const anchor = debug.anchor;
        const smoothedHand = debug.smoothed_hand;
        const controlMode = debug.control_mode;
        const isMirrored = this.settings.mirrorPreview;

        // Note on coordinate conversion for canvas:
        // When video and canvas are mirrored by CSS (scaleX(-1)),
        // points rendered at raw camera coordinates X_raw = width - X_user align with the mirrored video.
        // When unmirrored, points rendered at X_raw align with the unmirrored video.
        const toCanvasX = (userX) => {
            return width - userX;
        };

        const stateHex = {
            IDLE: '#9ca3af',
            ENGAGING: '#f59e0b',
            DRIVING: '#10b981',
            GRACE: '#f97316',
            ESTOP: '#ef4444'
        }[state] || '#10b981';

        // 1. Draw Skeleton if landmarks present
        if (results && results.landmarks && results.landmarks.length > 0) {
            const rawLms = results.landmarks[0];
            ctx.strokeStyle = 'rgba(245, 158, 11, 0.4)';
            ctx.lineWidth = 2;

            const connections = [
                [0, 1], [1, 2], [2, 3], [3, 4],
                [0, 5], [5, 6], [6, 7], [7, 8],
                [5, 9], [9, 10], [10, 11], [11, 12],
                [9, 13], [13, 14], [14, 15], [15, 16],
                [13, 17], [17, 18], [18, 19], [19, 20],
                [0, 17]
            ];

            ctx.beginPath();
            for (const [start, end] of connections) {
                const p1 = rawLms[start];
                const p2 = rawLms[end];
                ctx.moveTo(p1.x * width, p1.y * height);
                ctx.lineTo(p2.x * width, p2.y * height);
            }
            ctx.stroke();
        }

        // 2. Control Mode Visuals (Joystick vs Classic)
        if (controlMode === 'joystick' && anchor) {
            const ancX = toCanvasX(anchor[0]);
            const ancY = anchor[1];
            const scale = debug.smoothed_scale || 80.0;
            const fullScale = this.config?.mapping?.joystick_full_scale || 1.2;
            const deadzone = this.config?.mapping?.joystick_deadzone || 0.15;

            // Anchor Ring
            ctx.strokeStyle = '#38bdf8';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.arc(ancX, ancY, 8, 0, 2 * Math.PI);
            ctx.stroke();

            // Deadzone Circle
            ctx.strokeStyle = 'rgba(156, 163, 175, 0.5)';
            ctx.lineWidth = 1;
            ctx.setLineDash([4, 4]);
            ctx.beginPath();
            ctx.arc(ancX, ancY, deadzone * scale, 0, 2 * Math.PI);
            ctx.stroke();

            // Full-Scale Circle
            ctx.strokeStyle = 'rgba(56, 189, 248, 0.6)';
            ctx.lineWidth = 2;
            ctx.setLineDash([]);
            ctx.beginPath();
            ctx.arc(ancX, ancY, fullScale * scale, 0, 2 * Math.PI);
            ctx.stroke();

            // Vector line to smoothed hand
            if (smoothedHand) {
                const handX = toCanvasX(smoothedHand[0]);
                const handY = smoothedHand[1];
                ctx.strokeStyle = stateHex;
                ctx.lineWidth = 2;
                ctx.beginPath();
                ctx.moveTo(ancX, ancY);
                ctx.lineTo(handX, handY);
                ctx.stroke();
            }
        } else if (controlMode === 'classic') {
            // Neutral throttle guide line
            const neutralY = debug.neutral_y || (0.5 * height);
            ctx.strokeStyle = 'rgba(245, 158, 11, 0.3)';
            ctx.lineWidth = 1;
            ctx.setLineDash([6, 6]);
            ctx.beginPath();
            ctx.moveTo(0, neutralY);
            ctx.lineTo(width, neutralY);
            ctx.stroke();
            ctx.setLineDash([]);

            // Tilt gauge (top right corner)
            const gaugeX = width - 60;
            const gaugeY = 60;
            const gaugeR = 30;

            ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.arc(gaugeX, gaugeY, gaugeR, 0, 2 * Math.PI);
            ctx.stroke();

            const effTilt = (debug.smoothed_tilt || 0.0) - (debug.neutral_tilt || 0.0);
            const tiltRad = effTilt * (Math.PI / 180.0);
            // Tilt needle direction
            const needleDx = gaugeR * Math.sin(tiltRad);
            const needleDy = -gaugeR * Math.cos(tiltRad);
            const canvasNeedleDx = isMirrored ? -needleDx : needleDx;

            ctx.strokeStyle = stateHex;
            ctx.lineWidth = 3;
            ctx.beginPath();
            ctx.moveTo(gaugeX, gaugeY);
            ctx.lineTo(gaugeX + canvasNeedleDx, gaugeY + needleDy);
            ctx.stroke();
        }

        // 3. Smoothed Hand Position Dot
        if (smoothedHand) {
            const handX = toCanvasX(smoothedHand[0]);
            const handY = smoothedHand[1];
            ctx.fillStyle = stateHex;
            ctx.beginPath();
            ctx.arc(handX, handY, 7, 0, 2 * Math.PI);
            ctx.fill();
        }

        // 4. Debug readout (if enabled)
        if (this.settings.showDebug) {
            ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
            ctx.fillRect(10, 10, 180, 50);
            ctx.fillStyle = '#10b981';
            ctx.font = '11px monospace';
            ctx.fillText(`FPS: ${this.fps.toFixed(1)}`, 16, 28);
            ctx.fillText(`Latency: ${this.latencyMs.toFixed(1)} ms`, 16, 46);
        }
    }

    _showError(title, message) {
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

    clearLatches() {
        if (this.pipeline) {
            this.pipeline.clearLatches();
        }
    }

    reset() {
        this.linear = 0;
        this.angular = 0;
        this.flags = FLAG_LOW_CONFIDENCE;
        if (this.pipeline) {
            this.pipeline.reset();
        }
        if (this.canvasCtx && this.canvasElement) {
            this.canvasCtx.clearRect(0, 0, this.canvasElement.width, this.canvasElement.height);
        }
    }

    destroy() {
        this.reset();
        this.isReady = false;

        if (this.videoCallbackId !== null && this.videoElement && 'cancelVideoFrameCallback' in this.videoElement) {
            this.videoElement.cancelVideoFrameCallback(this.videoCallbackId);
            this.videoCallbackId = null;
        }

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
