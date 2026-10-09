import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from azure.ai.evaluation import (
    CoherenceEvaluator,
    FluencyEvaluator,
    GroundednessEvaluator,
    RelevanceEvaluator,
)

from ragpipeline.pipeline import answer

EVALUATOR_NAMES = ["relevance", "groundedness", "coherence", "fluency"]


def model_config():
    return {
        "azure_endpoint": os.environ["AZURE_OPENAI_ENDPOINT"],
        "api_key": os.environ["AZURE_OPENAI_API_KEY"],
        "azure_deployment": os.environ.get(
            "EVAL_DEPLOYMENT_NAME",
            os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-4.1-mini"),
        ),
    }


def load_golden_set():
    with open(ROOT / "eval" / "golden_set.jsonl", encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    limit = os.environ.get("GOLDEN_LIMIT")
    if limit:
        rows = rows[: int(limit)]
    return rows


def extract_score(result, key):
    if not isinstance(result, dict):
        return None
    for candidate in (key, f"gpt_{key}"):
        value = result.get(candidate)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def call_evaluator(name, evaluator, query, response, context):
    if name == "groundedness":
        return evaluator(query=query, response=response, context=context)
    if name == "fluency":
        return evaluator(response=response)
    return evaluator(query=query, response=response)


def mean(values):
    return sum(values) / len(values) if values else None


def main():
    mode = os.environ.get("RAG_MODE", "hybrid")
    cfg = model_config()
    evaluators = {
        "relevance": RelevanceEvaluator(cfg),
        "groundedness": GroundednessEvaluator(cfg),
        "coherence": CoherenceEvaluator(cfg),
        "fluency": FluencyEvaluator(cfg),
    }

    scores = {name: [] for name in EVALUATOR_NAMES}
    rows = []
    for item in load_golden_set():
        result = answer(item["query"], mode=mode)
        context = "\n\n".join(
            doc.get("parent_content") or doc.get("content", "") for doc in result["sources"]
        )
        row = {"query": item["query"], "answer": result["answer"], "scores": {}}
        for name, evaluator in evaluators.items():
            try:
                raw = call_evaluator(name, evaluator, item["query"], result["answer"], context)
                value = extract_score(raw, name)
            except Exception as exc:
                value = None
                row.setdefault("errors", {})[name] = str(exc)
            row["scores"][name] = value
            if value is not None:
                scores[name].append(value)
        rows.append(row)
        time.sleep(int(os.environ.get("EVAL_DELAY_SECONDS", "2")))

    metrics = {name: mean(values) for name, values in scores.items()}
    report = {"mode": mode, "n": len(rows), "metrics": metrics, "rows": rows}

    json_path = ROOT / "eval" / "quality_report.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# Evaluation report",
        "",
        f"- Mode: `{mode}`",
        f"- Questions: {len(rows)}",
        "",
        "| Metric | Mean |",
        "|---|---|",
    ]
    for name in EVALUATOR_NAMES:
        value = metrics[name]
        lines.append(f"| {name} | {'n/a' if value is None else f'{value:.2f}'} |")
    md_path = ROOT / "eval" / "quality_report.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"mode={mode} n={len(rows)}")
    for name in EVALUATOR_NAMES:
        value = metrics[name]
        print(f"  {name:14}{'n/a' if value is None else f'{value:.2f}'}")
    print(f"\nwrote {json_path}")
    print(f"wrote {md_path}")


if __name__ == "__main__":
    main()
