import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_THRESHOLDS = {
    "relevance": 3.0,
    "groundedness": 3.0,
    "coherence": 3.0,
    "fluency": 3.0,
}


def evaluate_gate(metrics, thresholds):
    failures = []
    for metric, threshold in thresholds.items():
        value = metrics.get(metric)
        if value is None or value < threshold:
            failures.append({"metric": metric, "value": value, "threshold": threshold})
    return failures


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default=str(ROOT / "eval" / "quality_report.json"))
    parser.add_argument("--relevance", type=float, default=DEFAULT_THRESHOLDS["relevance"])
    parser.add_argument("--groundedness", type=float, default=DEFAULT_THRESHOLDS["groundedness"])
    parser.add_argument("--coherence", type=float, default=DEFAULT_THRESHOLDS["coherence"])
    parser.add_argument("--fluency", type=float, default=DEFAULT_THRESHOLDS["fluency"])
    args = parser.parse_args()

    report_path = Path(args.report)
    if not report_path.exists():
        print(f"report not found: {report_path}")
        print("run `python eval/evaluate_quality.py` first")
        sys.exit(2)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    thresholds = {
        "relevance": args.relevance,
        "groundedness": args.groundedness,
        "coherence": args.coherence,
        "fluency": args.fluency,
    }

    failures = evaluate_gate(report.get("metrics", {}), thresholds)

    print(f"{'metric':14}{'value':>8}{'threshold':>11}")
    for metric, threshold in thresholds.items():
        value = report.get("metrics", {}).get(metric)
        print(f"{metric:14}{'n/a' if value is None else f'{value:.2f}':>8}{threshold:>11}")

    if failures:
        print("\nGATE FAILED:")
        for failure in failures:
            print(f"  {failure['metric']} = {failure['value']} (< {failure['threshold']})")
        sys.exit(1)

    print("\nGATE PASSED")


if __name__ == "__main__":
    main()
