/**
 * @file ws-client.js
 * @brief Resilient WebSocket client for ESP32 robot control with auto-reconnect and packet rate calculation.
 */

import { packMotionPacket } from './protocol.js';

export class RobotWsClient {
    /**
     * @param {Object} options
     * @param {string} [options.url] WebSocket endpoint URL (e.g. ws://192.168.1.150:80/ws)
     * @param {function(string, string): void} [options.onStatusChange] Callback(state, message)
     * @param {function(number): void} [options.onRateChange] Callback(rateHz)
     */
    constructor(options = {}) {
        this.url = options.url || this._getDefaultUrl();
        this.onStatusChange = options.onStatusChange || (() => {});
        this.onRateChange = options.onRateChange || (() => {});

        this.ws = null;
        this.seq = 0;
        this.state = 'disconnected'; // 'disconnected' | 'connecting' | 'connected'
        this.shouldReconnect = true;
        this.reconnectDelay = 500;
        this.maxReconnectDelay = 5000;
        this.reconnectTimer = null;

        // Rolling transmit rate calculation
        this.timestamps = [];
        this.rateHz = 0;
    }

    _getDefaultUrl() {
        const host = window.location.hostname || '127.0.0.1';
        const port = window.location.port ? window.location.port : '80';
        return `ws://${host}:${port}/ws`;
    }

    setUrl(url) {
        if (this.url !== url) {
            this.url = url;
            this.reconnect();
        }
    }

    connect() {
        this.shouldReconnect = true;
        if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
            return;
        }

        this._setStatus('connecting', `Connecting to ${this.url}...`);

        try {
            this.ws = new WebSocket(this.url);
            this.ws.binaryType = 'arraybuffer';

            this.ws.onopen = () => {
                this.reconnectDelay = 500;
                this._setStatus('connected', `Connected to ${this.url}`);
            };

            this.ws.onclose = (event) => {
                this._setStatus('disconnected', `Disconnected (code ${event.code})`);
                this._scheduleReconnect();
            };

            this.ws.onerror = (err) => {
                this._setStatus('disconnected', 'WebSocket connection error');
            };

            this.ws.onmessage = (event) => {
                // Future telemetry or ack handling
            };
        } catch (err) {
            this._setStatus('disconnected', `Connection failed: ${err.message}`);
            this._scheduleReconnect();
        }
    }

    disconnect() {
        this.shouldReconnect = false;
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        this._setStatus('disconnected', 'Manually disconnected');
    }

    reconnect() {
        this.disconnect();
        this.shouldReconnect = true;
        this.connect();
    }

    _scheduleReconnect() {
        if (!this.shouldReconnect || this.reconnectTimer) {
            return;
        }

        this.reconnectTimer = setTimeout(() => {
            this.reconnectTimer = null;
            this.reconnectDelay = Math.min(this.reconnectDelay * 1.5, this.maxReconnectDelay);
            this.connect();
        }, this.reconnectDelay);
    }

    _setStatus(state, message) {
        if (this.state !== state) {
            this.state = state;
            this.onStatusChange(state, message);
        }
    }

    /**
     * Sends a 10-byte binary MotionPacket.
     *
     * @param {number} linear -100 to 100
     * @param {number} angular -100 to 100
     * @param {number} [flags=0] bitmask
     * @returns {boolean} True if successfully sent
     */
    send(linear, angular, flags = 0) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            return false;
        }

        this.seq = (this.seq + 1) & 0xFFFF;
        const payload = packMotionPacket({
            seq: this.seq,
            linear,
            angular,
            flags,
        });

        try {
            this.ws.send(payload.buffer);
            this._recordPacketSent();
            return true;
        } catch (err) {
            console.warn('[WS Client] Send failed:', err);
            return false;
        }
    }

    _recordPacketSent() {
        const now = performance.now();
        this.timestamps.push(now);

        // Keep timestamps in the last 1 second window
        while (this.timestamps.length > 0 && now - this.timestamps[0] > 1000) {
            this.timestamps.shift();
        }

        this.rateHz = this.timestamps.length;
        this.onRateChange(this.rateHz);
    }

    isConnected() {
        return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
    }
}
