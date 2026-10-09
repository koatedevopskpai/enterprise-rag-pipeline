import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from azure.ai.evaluation import GroundednessEvaluator, RelevanceEvaluator

from ragpipeline.pipeline import answer


def model_config():
    return {
        "azure_endpoint": os.environ["AZURE_OPENAI_ENDPOINT"],
        "api_key": os.environ["AZURE_OPENAI_API_KEY"],
        "azure_deployment": os.environ.get(
            "EVAL_DEPLOYMENT_NAME",
            os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-4.1-mini"),
        ),
    }


def load_golden_set(path):
    with open(path, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    limit = os.environ.get("GOLDEN_LIMIT")
    if limit:
        rows = rows[: int(limit)]
    return rows


def run_safely(func, **kwargs):
    try:
        return func(**kwargs)
    except Exception as exc:
        return {"error": str(exc)}


def main():
    mode = os.environ.get("RAG_MODE", "hybrid")
    cfg = model_config()
    relevance = RelevanceEvaluator(cfg)
    groundedness = GroundednessEvaluator(cfg)

    rows = []
    for item in load_golden_set(ROOT / "eval" / "golden_set.jsonl"):
        result = answer(item["query"], mode=mode)
        context = "\n\n".join(
            doc.get("parent_content") or doc.get("content", "") for doc in result["sources"]
        )
        rows.append(
            {
                "query": item["query"],
                "answer": result["answer"],
                "sources": [doc["id"] for doc in result["sources"]],
                "relevance": run_safely(relevance, query=item["query"], response=result["answer"]),
                "groundedness": run_safely(
                    groundedness, query=item["query"], response=result["answer"], context=context
                ),
            }
        )
        time.sleep(int(os.environ.get("EVAL_DELAY_SECONDS", "2")))

    report = {"mode": mode, "count": len(rows), "rows": rows}
    out = ROOT / "eval" / "report.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    errors = sum(1 for r in rows if "error" in r["relevance"] or "error" in r["groundedness"])
    print(f"wrote {out} (mode={mode}, {len(rows)} rows, {errors} with evaluator errors)")


if __name__ == "__main__":
    main()
