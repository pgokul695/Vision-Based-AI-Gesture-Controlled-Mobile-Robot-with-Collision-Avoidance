/**
 * @file joystick-tab.js
 * @brief Continuous analog and 8-direction D-pad virtual joystick control tab.
 */

import { FLAG_ESTOP, FLAG_FUN_TRICK, FLAG_TURBO, FLAG_PRECISION } from './protocol.js';

export class JoystickTab {
    constructor() {
        this.container = null;
        this.linear = 0;   // -100 to 100
        this.angular = 0;  // -100 to 100

        this.turboHeld = false;
        this.precisionHeld = false;
        this.trickTriggered = false;

        this.isDpadMode = false; // continuous analog vs 8-direction stepped mode
        this.isDragging = false;
        this.pointerId = null;

        this.DEADZONE_RATIO = 0.10; // 10% deadzone
        this.MAX_RADIUS = 80;       // Max stick travel in pixels

        this._onPointerDown = this._onPointerDown.bind(this);
        this._onPointerMove = this._onPointerMove.bind(this);
        this._onPointerUp = this._onPointerUp.bind(this);
    }

    mount(container) {
        this.container = container;
        this.container.innerHTML = `
            <div class="joystick-control-panel">
                <div class="joystick-header">
                    <div class="mode-toggle-group">
                        <span class="hud-label">MODE:</span>
                        <button type="button" class="hud-btn mode-btn active" id="joy-analog-btn">ANALOG</button>
                        <button type="button" class="hud-btn mode-btn" id="joy-dpad-btn">8-WAY D-PAD</button>
                    </div>
                    <div class="stick-readout font-mono">
                        <span>X: <span id="joy-x-val">000</span>%</span>
                        <span>Y: <span id="joy-y-val">000</span>%</span>
                    </div>
                </div>

                <div class="joystick-arena">
                    <div class="joystick-base" id="joystick-base">
                        <div class="joystick-crosshair-x"></div>
                        <div class="joystick-crosshair-y"></div>
                        <div class="joystick-deadzone-circle"></div>
                        <div class="joystick-knob" id="joystick-knob">
                            <div class="knob-center-dot"></div>
                        </div>
                    </div>
                </div>

                <div class="modifiers-panel">
                    <button type="button" class="hud-btn mod-btn" id="joy-turbo-btn">
                        <span class="mod-title">TURBO</span>
                        <span class="mod-desc">HOLD 1.3x</span>
                    </button>
                    <button type="button" class="hud-btn mod-btn" id="joy-prec-btn">
                        <span class="mod-title">PRECISION</span>
                        <span class="mod-desc">HOLD 0.5x</span>
                    </button>
                    <button type="button" class="hud-btn mod-btn trick-btn" id="joy-trick-btn">
                        <span class="mod-title">SPIN TRICK</span>
                        <span class="mod-desc">1.5s FLOURISH</span>
                    </button>
                </div>
            </div>
        `;

        this._bindEvents();
    }

    _bindEvents() {
        const base = this.container.querySelector('#joystick-base');
        const knob = this.container.querySelector('#joystick-knob');
        const analogBtn = this.container.querySelector('#joy-analog-btn');
        const dpadBtn = this.container.querySelector('#joy-dpad-btn');

        // Mode toggles
        analogBtn.addEventListener('click', () => {
            this.isDpadMode = false;
            analogBtn.classList.add('active');
            dpadBtn.classList.remove('active');
        });

        dpadBtn.addEventListener('click', () => {
            this.isDpadMode = true;
            dpadBtn.classList.add('active');
            analogBtn.classList.remove('active');
        });

        // Pointer tracking on base
        base.addEventListener('pointerdown', this._onPointerDown);
        window.addEventListener('pointermove', this._onPointerMove);
        window.addEventListener('pointerup', this._onPointerUp);
        window.addEventListener('pointercancel', this._onPointerUp);

        // Modifiers
        const bindModHold = (btn, onDown, onUp) => {
            if (!btn) return;
            const start = (e) => {
                e.preventDefault();
                btn.setPointerCapture?.(e.pointerId);
                onDown();
            };
            const end = (e) => {
                e.preventDefault();
                btn.releasePointerCapture?.(e.pointerId);
                onUp();
            };
            btn.addEventListener('pointerdown', start);
            btn.addEventListener('pointerup', end);
            btn.addEventListener('pointercancel', end);
            btn.addEventListener('pointerleave', end);
        };

        const turboBtn = this.container.querySelector('#joy-turbo-btn');
        bindModHold(
            turboBtn,
            () => { this.turboHeld = true; turboBtn.classList.add('active'); },
            () => { this.turboHeld = false; turboBtn.classList.remove('active'); }
        );

        const precBtn = this.container.querySelector('#joy-prec-btn');
        bindModHold(
            precBtn,
            () => { this.precisionHeld = true; precBtn.classList.add('active'); },
            () => { this.precisionHeld = false; precBtn.classList.remove('active'); }
        );

        const trickBtn = this.container.querySelector('#joy-trick-btn');
        if (trickBtn) {
            trickBtn.addEventListener('pointerdown', (e) => {
                e.preventDefault();
                this.trickTriggered = true;
                trickBtn.classList.add('active');
                setTimeout(() => trickBtn.classList.remove('active'), 250);
            });
        }
    }

    _onPointerDown(e) {
        e.preventDefault();
        this.isDragging = true;
        this.pointerId = e.pointerId;
        const base = this.container.querySelector('#joystick-base');
        base.setPointerCapture?.(e.pointerId);
        this._updateKnobPosition(e.clientX, e.clientY);
    }

    _onPointerMove(e) {
        if (!this.isDragging || (this.pointerId !== null && e.pointerId !== this.pointerId)) {
            return;
        }
        e.preventDefault();
        this._updateKnobPosition(e.clientX, e.clientY);
    }

    _onPointerUp(e) {
        if (!this.isDragging || (this.pointerId !== null && e.pointerId !== this.pointerId)) {
            return;
        }
        e.preventDefault();
        const base = this.container?.querySelector('#joystick-base');
        try {
            base?.releasePointerCapture?.(e.pointerId);
        } catch (_) {}

        this.isDragging = false;
        this.pointerId = null;
        this._resetKnob();
    }

    _updateKnobPosition(clientX, clientY) {
        const base = this.container.querySelector('#joystick-base');
        const knob = this.container.querySelector('#joystick-knob');
        if (!base || !knob) return;

        const rect = base.getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;

        let dx = clientX - centerX;
        let dy = clientY - centerY;

        const distance = Math.sqrt(dx * dx + dy * dy);
        const radius = Math.min(distance, this.MAX_RADIUS);
        const angle = Math.atan2(dy, dx);

        if (distance > this.MAX_RADIUS) {
            dx = Math.cos(angle) * this.MAX_RADIUS;
            dy = Math.sin(angle) * this.MAX_RADIUS;
        }

        knob.style.transform = `translate(${dx}px, ${dy}px)`;

        // Normalize to -1.0 .. +1.0
        let normX = dx / this.MAX_RADIUS; // steering: right is positive
        let normY = -dy / this.MAX_RADIUS; // linear throttle: up is positive

        const mag = Math.sqrt(normX * normX + normY * normY);

        if (mag < this.DEADZONE_RATIO) {
            this.linear = 0;
            this.angular = 0;
        } else {
            // Rescale beyond deadzone to full 0..1
            const rescaledMag = (mag - this.DEADZONE_RATIO) / (1.0 - this.DEADZONE_RATIO);
            normX = (normX / mag) * rescaledMag;
            normY = (normY / mag) * rescaledMag;

            if (this.isDpadMode) {
                // Snap to 8 discrete compass directions (45 deg sectors)
                let deg = Math.atan2(normY, normX) * (180 / Math.PI);
                if (deg < 0) deg += 360;

                // Sectors: E (0), NE (45), N (90), NW (135), W (180), SW (225), S (270), SE (315)
                const sector = Math.round(deg / 45) % 8;
                const snapAngles = [0, 45, 90, 135, 180, 225, 270, 315];
                const snappedRad = (snapAngles[sector] * Math.PI) / 180;

                normX = Math.cos(snappedRad);
                normY = Math.sin(snappedRad);
            }

            this.angular = Math.round(Math.max(-100, Math.min(100, normX * 100)));
            this.linear = Math.round(Math.max(-100, Math.min(100, normY * 100)));
        }

        this._updateReadout(this.angular, this.linear);
    }

    _resetKnob() {
        const knob = this.container?.querySelector('#joystick-knob');
        if (knob) {
            knob.style.transform = `translate(0px, 0px)`;
        }
        this.linear = 0;
        this.angular = 0;
        this._updateReadout(0, 0);
    }

    _updateReadout(x, y) {
        const xEl = this.container?.querySelector('#joy-x-val');
        const yEl = this.container?.querySelector('#joy-y-val');
        if (xEl) xEl.textContent = (x >= 0 ? '+' : '') + x.toString().padStart(3, '0');
        if (yEl) yEl.textContent = (y >= 0 ? '+' : '') + y.toString().padStart(3, '0');
    }

    getCommand() {
        let flags = 0;
        if (this.precisionHeld) {
            flags |= FLAG_PRECISION;
        }
        if (this.turboHeld) {
            flags |= FLAG_TURBO;
        }
        if (this.trickTriggered) {
            flags |= FLAG_FUN_TRICK;
            this.trickTriggered = false; // One-shot
        }

        return {
            linear: this.linear,
            angular: this.angular,
            flags,
        };
    }

    reset() {
        this.isDragging = false;
        this.pointerId = null;
        this.turboHeld = false;
        this.precisionHeld = false;
        this.trickTriggered = false;
        this._resetKnob();

        if (this.container) {
            const activeMods = this.container.querySelectorAll('.mod-btn.active');
            activeMods.forEach(btn => btn.classList.remove('active'));
        }
    }

    destroy() {
        this.reset();
        window.removeEventListener('pointermove', this._onPointerMove);
        window.removeEventListener('pointerup', this._onPointerUp);
        window.removeEventListener('pointercancel', this._onPointerUp);
    }
}
