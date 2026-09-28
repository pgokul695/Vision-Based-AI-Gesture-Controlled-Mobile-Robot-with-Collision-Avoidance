import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { GesturePipeline } from '../js/gesture-pipeline.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const goldenPath = path.resolve(__dirname, '../../gesture-controller/tests/vectors/golden_vectors.json');
const goldenData = JSON.parse(fs.readFileSync(goldenPath, 'utf-8'));

test('Golden Vectors - JS Pipeline Parity with Python', async (t) => {
    for (const [scenarioName, scenario] of Object.entries(goldenData)) {
        await t.test(`Scenario: ${scenarioName}`, () => {
            const pipeline = new GesturePipeline(scenario.config);

            scenario.steps.forEach((step, idx) => {
                const result = pipeline.step(step.input_frame, step.t_ms);
                const exp = step.expected;

                const linDiff = Math.abs(result.linear - exp.linear);
                const angDiff = Math.abs(result.angular - exp.angular);

                assert.ok(
                    linDiff <= 1,
                    `Step ${idx} (${scenarioName}) linear mismatch: got ${result.linear}, expected ${exp.linear}`
                );
                assert.ok(
                    angDiff <= 1,
                    `Step ${idx} (${scenarioName}) angular mismatch: got ${result.angular}, expected ${exp.angular}`
                );
                assert.strictEqual(
                    result.flags,
                    exp.flags,
                    `Step ${idx} (${scenarioName}) flags mismatch: got 0x${result.flags.toString(16)}, expected 0x${exp.flags.toString(16)}`
                );
                assert.strictEqual(
                    result.debug.state,
                    exp.state,
                    `Step ${idx} (${scenarioName}) state mismatch: got ${result.debug.state}, expected ${exp.state}`
                );
            });
        });
    }
});
