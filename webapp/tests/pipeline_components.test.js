import test from 'node:test';
import assert from 'node:assert/strict';

import {
    OneEuroFilter,
    SlewLimiter,
    GesturePipeline,
    applyAxisShaping,
    FLAG_ESTOP,
    FLAG_LOW_CONFIDENCE,
    FLAG_FUN_TRICK,
    FLAG_TURBO,
    FLAG_PRECISION
} from '../js/gesture-pipeline.js';

test('Component: OneEuroFilter smoothing & derivative adaptation', () => {
    const f = new OneEuroFilter(1.0, 0.01, 1.0);
    const val0 = f.filter(10.0, 0);
    assert.strictEqual(val0, 10.0);

    const val1 = f.filter(10.5, 50);
    assert.ok(val1 > 10.0 && val1 < 10.5);

    f.reset();
    f.filter(0.0, 0);
    const fastVal = f.filter(100.0, 50);
    assert.ok(fastVal > 10.0);
});

test('Component: SlewLimiter asymmetric rate & sign change through zero', () => {
    const limiter = new SlewLimiter(250.0, 800.0, 400.0);

    limiter.step(0, 0, 100);
    const [lin1] = limiter.step(100, 0, 300);
    assert.strictEqual(lin1, 50);

    const [lin2] = limiter.step(0, 0, 350);
    assert.strictEqual(lin2, 10);

    const [lin3] = limiter.step(-50, 0, 400);
    assert.strictEqual(lin3, -9);
});

test('Component: applyAxisShaping deadzone, expo, clamping', () => {
    // Within deadzone
    assert.strictEqual(applyAxisShaping(0.05, 1.0, 0.10, 1.0, 0.4), 0);

    // Smooth onset above deadzone
    const val = applyAxisShaping(0.12, 1.0, 0.10, 1.0, 0.4);
    assert.ok(val > 0 && val < 5);

    // At full scale
    assert.strictEqual(applyAxisShaping(1.0, 1.0, 0.10, 1.0, 0.4), 100);

    // Beyond full scale clamped
    assert.strictEqual(applyAxisShaping(1.5, 1.0, 0.10, 1.0, 0.4), 100);

    // Symmetry (reverse_scale = 1.0)
    assert.strictEqual(applyAxisShaping(-1.0, 1.0, 0.10, 1.0, 0.4), -100);

    // Reverse scale limits negative output to 60%
    assert.strictEqual(applyAxisShaping(-1.0, 1.0, 0.10, 1.0, 0.4, 0.60), -60);
    // Beyond full scale clamped at -60
    assert.strictEqual(applyAxisShaping(-2.0, 1.0, 0.10, 1.0, 0.4, 0.60), -60);
});

test('Component: cross-axis coupling suppression', () => {
    const p = new GesturePipeline();
    p.mapCfg.cross_axis_coupling_ratio = 2.0;
    p.mapCfg.tilt_neutral = 'fixed';

    const [lin, ang] = p._computeMappingTraced(320.0, 140.0, 6.0, 80.0, 480.0);
    assert.strictEqual(Math.abs(lin), 100);
    assert.strictEqual(ang, 0); // Angular attenuated to 0 because linear is > 4x angular

    // When disabled (0.0), no attenuation
    p.mapCfg.cross_axis_coupling_ratio = 0.0;
    const [lin2, ang2] = p._computeMappingTraced(320.0, 140.0, 6.0, 80.0, 480.0);
    assert.strictEqual(Math.abs(lin2), 100);
    assert.notStrictEqual(ang2, 0);
});

