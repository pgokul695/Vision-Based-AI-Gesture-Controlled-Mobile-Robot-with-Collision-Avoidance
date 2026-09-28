"""Pytest suite verifying GesturePipeline against deterministic golden vectors."""

import json
from pathlib import Path
import pytest

from gesture.pipeline import GesturePipeline

GOLDEN_PATH = Path(__file__).resolve().parent / "vectors" / "golden_vectors.json"


@pytest.fixture(scope="module")
def golden_data():
    with open(GOLDEN_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_all_golden_scenarios(golden_data):
    for scenario_name, scenario in golden_data.items():
        pipeline = GesturePipeline(scenario["config"])
        for idx, step in enumerate(scenario["steps"]):
            result = pipeline.step(step["input_frame"], step["t_ms"])
            exp = step["expected"]

            assert abs(result["linear"] - exp["linear"]) <= 1, (
                f"{scenario_name} step {idx}: linear got {result['linear']}, expected {exp['linear']}"
            )
            assert abs(result["angular"] - exp["angular"]) <= 1, (
                f"{scenario_name} step {idx}: angular got {result['angular']}, expected {exp['angular']}"
            )
            assert result["flags"] == exp["flags"], (
                f"{scenario_name} step {idx}: flags got {result['flags']}, expected {exp['flags']}"
            )
            assert result["debug"]["state"] == exp["state"], (
                f"{scenario_name} step {idx}: state got {result['debug']['state']}, expected {exp['state']}"
            )
