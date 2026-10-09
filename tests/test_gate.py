import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval"))

from gate import evaluate_gate


def test_gate_passes_when_all_above():
    metrics = {"relevance": 4.0, "groundedness": 4.5, "coherence": 3.5, "fluency": 3.1}
    thresholds = {"relevance": 3.0, "groundedness": 3.0, "coherence": 3.0, "fluency": 3.0}
    assert evaluate_gate(metrics, thresholds) == []


def test_gate_fails_below_threshold():
    metrics = {"relevance": 2.0, "groundedness": 4.0}
    failures = evaluate_gate(metrics, {"relevance": 3.0, "groundedness": 3.0})
    assert len(failures) == 1
    assert failures[0]["metric"] == "relevance"


def test_gate_fails_on_missing_metric():
    failures = evaluate_gate({}, {"relevance": 3.0})
    assert failures[0]["value"] is None
