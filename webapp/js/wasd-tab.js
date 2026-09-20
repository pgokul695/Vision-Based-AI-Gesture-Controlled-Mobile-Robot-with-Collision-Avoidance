/**
 * @file wasd-tab.js
 * @brief Virtual and physical WASD keyboard driving tab.
 *
 * Implements differential steering matching gesture-controller/tools/wasd_drive.py:
 * - W: Linear +80%
 * - S: Linear -80%
 * - A: Angular -60%
 * - D: Angular +60%
 * - Chording (e.g. W+D -> +80, +60)
 * - Opposing key cancellation (W+S -> 0, A+D -> 0)
 * - Modifiers for Turbo (1.3x) and Precision (0.5x)
 * - Fun trick one-shot trigger
 */

import { FLAG_ESTOP, FLAG_FUN_TRICK, FLAG_TURBO, FLAG_PRECISION } from './protocol.js';

export class WasdTab {
    constructor() {
        this.container = null;
        this.heldKeys = new Set();
        this.virtualHeldKeys = new Set();

        this.turboHeld = false;
        this.precisionHeld = false;
        this.trickTriggered = false;
        this.estopActive = false;

        this.LINEAR_SPEED = 80;
        this.ANGULAR_SPEED = 60;

        this._onKeyDown = this._onKeyDown.bind(this);
        this._onKeyUp = this._onKeyUp.bind(this);
        this._onWindowBlur = this._onWindowBlur.bind(this);
        this.isActive = false;
    }

    mount(container) {
        this.container = container;
        this.isActive = true;
        this.container.innerHTML = `
            <div class="wasd-control-panel">
                <div class="wasd-instructions">
                    <span class="hud-tag">KEYBOARD OR TOUCH ACTIVE</span>
                    <p class="hud-hint">Use [W] [A] [S] [D] or touch buttons below. [Space] to stop.</p>
                </div>

                <div class="wasd-cluster">
                    <div class="wasd-row wasd-top-row">
                        <button type="button" class="hud-btn wasd-btn wasd-w" data-key="w" aria-label="Forward (W)">
                            <span class="btn-letter">W</span>
                            <span class="btn-sub">FWD</span>
                        </button>
                    </div>
                    <div class="wasd-row wasd-mid-row">
                        <button type="button" class="hud-btn wasd-btn wasd-a" data-key="a" aria-label="Left (A)">
                            <span class="btn-letter">A</span>
                            <span class="btn-sub">LEFT</span>
                        </button>
                        <button type="button" class="hud-btn wasd-btn wasd-s" data-key="s" aria-label="Reverse (S)">
                            <span class="btn-letter">S</span>
                            <span class="btn-sub">REV</span>
                        </button>
                        <button type="button" class="hud-btn wasd-btn wasd-d" data-key="d" aria-label="Right (D)">
                            <span class="btn-letter">D</span>
                            <span class="btn-sub">RIGHT</span>
                        </button>
                    </div>
                    <div class="wasd-row wasd-bot-row">
                        <button type="button" class="hud-btn wasd-space-btn" data-key=" " aria-label="Brake Space">
                            <span class="btn-letter">SPACE</span>
                            <span class="btn-sub">BRAKE / HALT</span>
                        </button>
                    </div>
                </div>

                <div class="modifiers-panel">
                    <button type="button" class="hud-btn mod-btn" id="wasd-turbo-btn">
                        <span class="mod-title">TURBO</span>
                        <span class="mod-desc">HOLD 1.3x [SHIFT]</span>
                    </button>
                    <button type="button" class="hud-btn mod-btn" id="wasd-prec-btn">
                        <span class="mod-title">PRECISION</span>
                        <span class="mod-desc">HOLD 0.5x [CTRL]</span>
                    </button>
                    <button type="button" class="hud-btn mod-btn trick-btn" id="wasd-trick-btn">
                        <span class="mod-title">SPIN TRICK</span>
                        <span class="mod-desc">1.5s FLOURISH [T]</span>
                    </button>
                </div>
            </div>
        `;

        this._bindEvents();
    }

    _bindEvents() {
        // Physical keyboard event listeners
        window.addEventListener('keydown', this._onKeyDown);
        window.addEventListener('keyup', this._onKeyUp);
        window.addEventListener('blur', this._onWindowBlur);

        // Virtual buttons pointer events
        const bindKeyHold = (btn, key) => {
            if (!btn) return;
            const start = (e) => {
                e.preventDefault();
                btn.setPointerCapture?.(e.pointerId);
                this.virtualHeldKeys.add(key);
                btn.classList.add('active');
            };
            const end = (e) => {
                e.preventDefault();
                btn.releasePointerCapture?.(e.pointerId);
                this.virtualHeldKeys.delete(key);
                btn.classList.remove('active');
            };

            btn.addEventListener('pointerdown', start);
            btn.addEventListener('pointerup', end);
            btn.addEventListener('pointercancel', end);
            btn.addEventListener('pointerleave', end);
        };

        const keyBtns = this.container.querySelectorAll('[data-key]');
        keyBtns.forEach(btn => {
            const key = btn.getAttribute('data-key').toLowerCase();
            bindKeyHold(btn, key);
        });

        // Modifier buttons
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

        const turboBtn = this.container.querySelector('#wasd-turbo-btn');
        bindModHold(
            turboBtn,
            () => { this.turboHeld = true; turboBtn.classList.add('active'); },
            () => { this.turboHeld = false; turboBtn.classList.remove('active'); }
        );

        const precBtn = this.container.querySelector('#wasd-prec-btn');
        bindModHold(
            precBtn,
            () => { this.precisionHeld = true; precBtn.classList.add('active'); },
            () => { this.precisionHeld = false; precBtn.classList.remove('active'); }
        );

        const trickBtn = this.container.querySelector('#wasd-trick-btn');
        if (trickBtn) {
            trickBtn.addEventListener('pointerdown', (e) => {
                e.preventDefault();
                this.trickTriggered = true;
                trickBtn.classList.add('active');
                setTimeout(() => trickBtn.classList.remove('active'), 250);
            });
        }
    }

    _onKeyDown(e) {
        if (!this.isActive) return;
        // Ignore typing in input fields
        if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) {
            return;
        }

        const key = e.key.toLowerCase();

        if (['w', 'a', 's', 'd', ' '].includes(key)) {
            e.preventDefault();
            this.heldKeys.add(key);
            this._highlightKey(key, true);
        } else if (e.key === 'Shift') {
            this.turboHeld = true;
            this._highlightModifier('#wasd-turbo-btn', true);
        } else if (e.key === 'Control') {
            this.precisionHeld = true;
            this._highlightModifier('#wasd-prec-btn', true);
        } else if (key === 't') {
            this.trickTriggered = true;
            const btn = this.container?.querySelector('#wasd-trick-btn');
            if (btn) {
                btn.classList.add('active');
                setTimeout(() => btn.classList.remove('active'), 250);
            }
        }
    }

    _onKeyUp(e) {
        if (!this.isActive) return;
        const key = e.key.toLowerCase();

        if (['w', 'a', 's', 'd', ' '].includes(key)) {
            e.preventDefault();
            this.heldKeys.delete(key);
            this._highlightKey(key, false);
        } else if (e.key === 'Shift') {
            this.turboHeld = false;
            this._highlightModifier('#wasd-turbo-btn', false);
        } else if (e.key === 'Control') {
            this.precisionHeld = false;
            this._highlightModifier('#wasd-prec-btn', false);
        }
    }

    _onWindowBlur() {
        this.reset();
    }

    _highlightKey(key, active) {
        if (!this.container) return;
        const btn = this.container.querySelector(`[data-key="${key}"]`);
        if (btn) {
            if (active) btn.classList.add('key-pressed');
            else btn.classList.remove('key-pressed');
        }
    }

    _highlightModifier(selector, active) {
        if (!this.container) return;
        const btn = this.container.querySelector(selector);
        if (btn) {
            if (active) btn.classList.add('active');
            else btn.classList.remove('active');
        }
    }

    getCommand() {
        const combined = new Set([...this.heldKeys, ...this.virtualHeldKeys]);

        let linear = 0;
        let angular = 0;
        let flags = 0;

        // Space acts as brake/emergency stop
        if (combined.has(' ')) {
            return { linear: 0, angular: 0, flags: FLAG_ESTOP };
        }

        const hasW = combined.has('w');
        const hasS = combined.has('s');
        const hasA = combined.has('a');
        const hasD = combined.has('d');

        if (hasW && !hasS) {
            linear = this.LINEAR_SPEED;
        } else if (hasS && !hasW) {
            linear = -this.LINEAR_SPEED;
        }

        if (hasA && !hasD) {
            angular = -this.ANGULAR_SPEED;
        } else if (hasD && !hasA) {
            angular = this.ANGULAR_SPEED;
        }

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

        return { linear, angular, flags };
    }

    reset() {
        this.heldKeys.clear();
        this.virtualHeldKeys.clear();
        this.turboHeld = false;
        this.precisionHeld = false;
        this.trickTriggered = false;
        this.estopActive = false;

        if (this.container) {
            const activeElems = this.container.querySelectorAll('.active, .key-pressed');
            activeElems.forEach(el => el.classList.remove('active', 'key-pressed'));
        }
    }

    destroy() {
        this.isActive = false;
        this.reset();
        window.removeEventListener('keydown', this._onKeyDown);
        window.removeEventListener('keyup', this._onKeyUp);
        window.removeEventListener('blur', this._onWindowBlur);
    }
}
