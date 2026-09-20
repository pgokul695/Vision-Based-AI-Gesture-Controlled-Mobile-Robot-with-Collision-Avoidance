/**
 * @file app.js
 * @brief Master application controller for the ESP32 Mobile Robot Web App.
 *
 * Enforces safety invariants:
 * 1. Zero motion command dispatched immediately upon any tab switch.
 * 2. Backgrounding / window blur halts robot instantly.
 * 3. Continuous 20Hz deadman dispatch loop.
 */

import { RobotWsClient } from './ws-client.js';
import { FLAG_ESTOP, FLAG_FUN_TRICK, FLAG_TURBO, FLAG_PRECISION } from './protocol.js';
import { TraditionalNavTab } from './traditional-nav-tab.js';
import { WasdTab } from './wasd-tab.js';
import { JoystickTab } from './joystick-tab.js';
import { GestureTab } from './gesture-tab.js';

class RobotApp {
    constructor() {
        this.wsClient = null;
        this.tabs = {};
        this.currentTabId = 'traditional';
        this.activeTab = null;

        // Persistent footer overrides
        this.globalEstopActive = false;
        this.globalTrickTriggered = false;

        // Master loop timer
        this.loopTimer = null;
        this.TICK_INTERVAL_MS = 50; // 20Hz

        // Telemetry cache
        this.lastLinear = 0;
        this.lastAngular = 0;
        this.lastFlags = 0;
    }

    init() {
        this._initWebSocket();
        this._initTabs();
        this._bindUI();
        this._bindSafetyWatchdogs();
        this._startMasterLoop();
    }

    _initWebSocket() {
        this.wsClient = new RobotWsClient({
            onStatusChange: (state, msg) => this._updateConnectionStatus(state, msg),
            onRateChange: (rateHz) => this._updateRateDisplay(rateHz)
        });
        this.wsClient.connect();
    }

    _initTabs() {
        this.tabs = {
            traditional: new TraditionalNavTab(),
            wasd: new WasdTab(),
            joystick: new JoystickTab(),
            gesture: new GestureTab()
        };

        const viewContainer = document.getElementById('tab-view-container');
        this.activeTab = this.tabs[this.currentTabId];
        this.activeTab.mount(viewContainer);
    }

    _bindUI() {
        // Tab buttons
        const tabBtns = document.querySelectorAll('.hud-tab-btn');
        tabBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                const targetTab = btn.getAttribute('data-tab');
                if (targetTab && targetTab !== this.currentTabId) {
                    this.switchTab(targetTab);
                }
            });
        });

        // Global Footer Emergency Stop
        const globalEstopBtn = document.getElementById('global-estop-btn');
        if (globalEstopBtn) {
            const startEstop = (e) => {
                e.preventDefault();
                this.globalEstopActive = true;
                globalEstopBtn.classList.add('active');
                // Immediate stop
                this.wsClient.send(0, 0, FLAG_ESTOP);
            };
            const endEstop = (e) => {
                e.preventDefault();
                this.globalEstopActive = false;
                globalEstopBtn.classList.remove('active');
            };

            globalEstopBtn.addEventListener('pointerdown', startEstop);
            globalEstopBtn.addEventListener('pointerup', endEstop);
            globalEstopBtn.addEventListener('pointercancel', endEstop);
            globalEstopBtn.addEventListener('pointerleave', endEstop);
        }

        // Global Footer Spin Trick
        const globalTrickBtn = document.getElementById('global-trick-btn');
        if (globalTrickBtn) {
            globalTrickBtn.addEventListener('pointerdown', (e) => {
                e.preventDefault();
                this.globalTrickTriggered = true;
                globalTrickBtn.classList.add('active');
                setTimeout(() => globalTrickBtn.classList.remove('active'), 250);
            });
        }

        // Connection Settings Modal
        const settingsBtn = document.getElementById('settings-btn');
        const settingsModal = document.getElementById('settings-modal');
        const closeSettingsBtn = document.getElementById('close-settings-btn');
        const saveSettingsBtn = document.getElementById('save-settings-btn');
        const cancelSettingsBtn = document.getElementById('cancel-settings-btn');
        const wsUrlInput = document.getElementById('ws-url-input');

        if (wsUrlInput) {
            wsUrlInput.value = this.wsClient.url;
        }

        if (settingsBtn && settingsModal) {
            settingsBtn.addEventListener('click', () => {
                if (wsUrlInput) wsUrlInput.value = this.wsClient.url;
                settingsModal.classList.remove('hidden');
            });
        }

        const closeModal = () => {
            if (settingsModal) settingsModal.classList.add('hidden');
        };

        if (closeSettingsBtn) closeSettingsBtn.addEventListener('click', closeModal);
        if (cancelSettingsBtn) cancelSettingsBtn.addEventListener('click', closeModal);

        if (saveSettingsBtn && settingsModal && wsUrlInput) {
            saveSettingsBtn.addEventListener('click', () => {
                const newUrl = wsUrlInput.value.trim();
                if (newUrl) {
                    this.wsClient.setUrl(newUrl);
                }
                settingsModal.classList.add('hidden');
            });
        }
    }

    _bindSafetyWatchdogs() {
        // SAFETY INVARIANT: Halt robot immediately when page loses focus or screen is locked
        const haltOnBackground = () => {
            console.warn('[Safety Watchdog] Visibility lost or window blurred -> halting robot');
            this.wsClient.send(0, 0, 0);
            if (this.activeTab) {
                this.activeTab.reset();
            }
        };

        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                haltOnBackground();
            }
        });

        window.addEventListener('blur', haltOnBackground);
        window.addEventListener('pagehide', haltOnBackground);
    }

    /**
     * SAFETY INVARIANT: Switch tabs safely by stopping the robot,
     * resetting previous tab state, and mounting the target tab.
     */
    switchTab(tabId) {
        if (!this.tabs[tabId]) return;

        // 1. Mandatory immediate zero command
        this.wsClient.send(0, 0, 0);

        // 2. Teardown current tab
        if (this.activeTab) {
            if (typeof this.activeTab.destroy === 'function') {
                this.activeTab.destroy();
            } else {
                this.activeTab.reset();
            }
        }

        // 3. Update active tab UI indicator
        document.querySelectorAll('.hud-tab-btn').forEach(btn => {
            if (btn.getAttribute('data-tab') === tabId) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        // 4. Mount new tab
        this.currentTabId = tabId;
        this.activeTab = this.tabs[tabId];
        const viewContainer = document.getElementById('tab-view-container');
        viewContainer.innerHTML = '';
        this.activeTab.mount(viewContainer);
    }

    _startMasterLoop() {
        if (this.loopTimer) clearInterval(this.loopTimer);

        this.loopTimer = setInterval(() => {
            this._tick();
        }, this.TICK_INTERVAL_MS);
    }

    _tick() {
        if (!this.activeTab) return;

        let cmd = this.activeTab.getCommand();
        let linear = cmd.linear || 0;
        let angular = cmd.angular || 0;
        let flags = cmd.flags || 0;

        // Global footer overrides
        if (this.globalEstopActive) {
            flags |= FLAG_ESTOP;
            linear = 0;
            angular = 0;
        }

        if (this.globalTrickTriggered) {
            flags |= FLAG_FUN_TRICK;
            this.globalTrickTriggered = false; // One-shot
        }

        // Dispatch over WebSocket
        this.wsClient.send(linear, angular, flags);

        // Update HUD telemetry
        this.lastLinear = linear;
        this.lastAngular = angular;
        this.lastFlags = flags;
        this._updateTelemetryDisplay(linear, angular, flags);
    }

    _updateConnectionStatus(state, msg) {
        const dot = document.getElementById('status-dot');
        const text = document.getElementById('status-text');

        if (dot) {
            dot.className = `status-dot ${state}`;
        }
        if (text) {
            text.textContent = state.toUpperCase();
        }
    }

    _updateRateDisplay(rateHz) {
        const rateEl = document.getElementById('packet-rate');
        if (rateEl) {
            rateEl.textContent = `${rateHz} Hz`;
        }
    }

    _updateTelemetryDisplay(linear, angular, flags) {
        const linEl = document.getElementById('telem-linear');
        const angEl = document.getElementById('telem-angular');
        const modeBadge = document.getElementById('telem-mode-badge');

        if (linEl) {
            const sign = linear >= 0 ? '+' : '';
            linEl.textContent = `L:${sign}${linear.toString().padStart(3, '0')}%`;
        }
        if (angEl) {
            const sign = angular >= 0 ? '+' : '';
            angEl.textContent = `A:${sign}${angular.toString().padStart(3, '0')}%`;
        }

        if (modeBadge) {
            if (flags & FLAG_ESTOP) {
                modeBadge.textContent = 'E-STOP';
                modeBadge.className = 'hud-badge badge-estop';
            } else if (flags & FLAG_TURBO) {
                modeBadge.textContent = 'TURBO';
                modeBadge.className = 'hud-badge badge-turbo';
            } else if (flags & FLAG_PRECISION) {
                modeBadge.textContent = 'PREC';
                modeBadge.className = 'hud-badge badge-prec';
            } else if (flags & FLAG_FUN_TRICK) {
                modeBadge.textContent = 'TRICK';
                modeBadge.className = 'hud-badge badge-trick';
            } else {
                modeBadge.textContent = 'NORM';
                modeBadge.className = 'hud-badge badge-normal';
            }
        }
    }
}

// Bootstrap on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    const app = new RobotApp();
    app.init();
    window._robotApp = app;
});
