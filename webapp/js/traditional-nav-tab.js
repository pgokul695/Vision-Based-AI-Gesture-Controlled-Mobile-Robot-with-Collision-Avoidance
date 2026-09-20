/**
 * @file traditional-nav-tab.js
 * @brief Traditional remote control nav tab with pointer deadman switch controls.
 */

import { FLAG_ESTOP, FLAG_FUN_TRICK, FLAG_TURBO, FLAG_PRECISION } from './protocol.js';

export class TraditionalNavTab {
    constructor() {
        this.activeDirection = null; // 'forward' | 'reverse' | 'left' | 'right'
        this.turboHeld = false;
        this.precisionHeld = false;
        this.trickTriggered = false;
        this.estopActive = false;

        // Constants matching physical WASD / RC defaults
        this.LINEAR_SPEED = 80;
        this.ANGULAR_SPEED = 60;
    }

    mount(container) {
        this.container = container;
        this.container.innerHTML = `
            <div class="nav-control-panel">
                <div class="dpad-container">
                    <button type="button" class="hud-btn dpad-btn dpad-up" data-dir="forward" aria-label="Forward">
                        <span class="btn-icon">▲</span>
                        <span class="btn-label">FWD</span>
                    </button>
                    <div class="dpad-middle-row">
                        <button type="button" class="hud-btn dpad-btn dpad-left" data-dir="left" aria-label="Turn Left">
                            <span class="btn-icon">◀</span>
                            <span class="btn-label">LEFT</span>
                        </button>
                        <button type="button" class="hud-btn dpad-btn dpad-stop" id="trad-stop-btn" aria-label="Stop">
                            <span class="btn-icon">■</span>
                            <span class="btn-label">STOP</span>
                        </button>
                        <button type="button" class="hud-btn dpad-btn dpad-right" data-dir="right" aria-label="Turn Right">
                            <span class="btn-icon">▶</span>
                            <span class="btn-label">RIGHT</span>
                        </button>
                    </div>
                    <button type="button" class="hud-btn dpad-btn dpad-down" data-dir="reverse" aria-label="Reverse">
                        <span class="btn-icon">▼</span>
                        <span class="btn-label">REV</span>
                    </button>
                </div>

                <div class="modifiers-panel">
                    <button type="button" class="hud-btn mod-btn" id="trad-turbo-btn">
                        <span class="mod-title">TURBO</span>
                        <span class="mod-desc">HOLD 1.3x</span>
                    </button>
                    <button type="button" class="hud-btn mod-btn" id="trad-prec-btn">
                        <span class="mod-title">PRECISION</span>
                        <span class="mod-desc">HOLD 0.5x</span>
                    </button>
                    <button type="button" class="hud-btn mod-btn trick-btn" id="trad-trick-btn">
                        <span class="mod-title">SPIN TRICK</span>
                        <span class="mod-desc">1.5s FLOURISH</span>
                    </button>
                </div>
            </div>
        `;

        this._bindEvents();
    }

    _bindEvents() {
        const bindHold = (btn, onDown, onUp) => {
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

        // Direction buttons
        const dirButtons = this.container.querySelectorAll('[data-dir]');
        dirButtons.forEach(btn => {
            const dir = btn.getAttribute('data-dir');
            bindHold(
                btn,
                () => {
                    this.activeDirection = dir;
                    btn.classList.add('active');
                },
                () => {
                    if (this.activeDirection === dir) {
                        this.activeDirection = null;
                    }
                    btn.classList.remove('active');
                }
            );
        });

        // Stop button
        const stopBtn = this.container.querySelector('#trad-stop-btn');
        if (stopBtn) {
            bindHold(
                stopBtn,
                () => {
                    this.activeDirection = null;
                    this.estopActive = true;
                    stopBtn.classList.add('active');
                },
                () => {
                    this.estopActive = false;
                    stopBtn.classList.remove('active');
                }
            );
        }

        // Turbo modifier
        const turboBtn = this.container.querySelector('#trad-turbo-btn');
        bindHold(
            turboBtn,
            () => {
                this.turboHeld = true;
                turboBtn.classList.add('active');
            },
            () => {
                this.turboHeld = false;
                turboBtn.classList.remove('active');
            }
        );

        // Precision modifier
        const precBtn = this.container.querySelector('#trad-prec-btn');
        bindHold(
            precBtn,
            () => {
                this.precisionHeld = true;
                precBtn.classList.add('active');
            },
            () => {
                this.precisionHeld = false;
                precBtn.classList.remove('active');
            }
        );

        // Fun trick trigger (one-shot click/tap)
        const trickBtn = this.container.querySelector('#trad-trick-btn');
        if (trickBtn) {
            trickBtn.addEventListener('pointerdown', (e) => {
                e.preventDefault();
                this.trickTriggered = true;
                trickBtn.classList.add('active');
                setTimeout(() => trickBtn.classList.remove('active'), 250);
            });
        }
    }

    /**
     * Reads current commanded motion from this tab.
     * Called by the 20Hz master loop.
     */
    getCommand() {
        let linear = 0;
        let angular = 0;
        let flags = 0;

        if (this.estopActive) {
            return { linear: 0, angular: 0, flags: FLAG_ESTOP };
        }

        if (this.activeDirection === 'forward') {
            linear = this.LINEAR_SPEED;
        } else if (this.activeDirection === 'reverse') {
            linear = -this.LINEAR_SPEED;
        } else if (this.activeDirection === 'left') {
            angular = -this.ANGULAR_SPEED;
        } else if (this.activeDirection === 'right') {
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
        this.activeDirection = null;
        this.turboHeld = false;
        this.precisionHeld = false;
        this.trickTriggered = false;
        this.estopActive = false;
        if (this.container) {
            const activeBtns = this.container.querySelectorAll('.active');
            activeBtns.forEach(btn => btn.classList.remove('active'));
        }
    }
}
