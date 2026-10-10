import json
import math
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from azure.ai.evaluation import GroundednessEvaluator, RelevanceEvaluator

from ragpipeline.strategies import STRATEGIES
from ragpipeline.synthesize import synthesize_answer

MODES = ["bm25", "vector", "hybrid", "hybrid_rerank"]


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
    golden_path = Path(os.environ.get("GOLDEN_PATH", "eval/golden_set.jsonl"))
    if not golden_path.is_absolute():
        golden_path = ROOT / golden_path
    with open(golden_path, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    limit = os.environ.get("GOLDEN_LIMIT")
    if limit:
        rows = rows[: int(limit)]
    query_type = os.environ.get("QUERY_TYPE")
    if query_type:
        rows = [row for row in rows if row.get("type") == query_type]
    return rows


def extract_score(result, key):
    if not isinstance(result, dict):
        return None
    for candidate in (key, f"gpt_{key}"):
        value = result.get(candidate)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def run_safely(func, **kwargs):
    try:
        return func(**kwargs)
    except Exception as exc:
        return {"error": str(exc)}


def hit_metrics(sources, expected):
    ids = [doc.get("source_id") for doc in sources]
    if expected and expected in ids:
        rank = ids.index(expected) + 1
        return 1.0, 1.0 / rank, rank
    return 0.0, 0.0, None


def mean(values):
    return sum(values) / len(values) if values else None


def fmt(value):
    return "n/a" if value is None else f"{value:.2f}"


def main():
    skip_eval = os.environ.get("SKIP_LLM_EVAL", "0") == "1"
    cfg = model_config()
    relevance = RelevanceEvaluator(cfg) if not skip_eval else None
    groundedness = GroundednessEvaluator(cfg) if not skip_eval else None
    golden = load_golden_set()

    summary = {}
    details = {}

    for mode in MODES:
        hits = []
        hits1 = []
        rrs = []
        ndcgs = []
        rel_scores = []
        grd_scores = []
        rows = []
        for item in golden:
            try:
                sources = STRATEGIES[mode](item["query"])
            except Exception as exc:
                rows.append({"query": item["query"], "error": str(exc)})
                continue

            hit, rr, rank = hit_metrics(sources, item.get("expected_source"))
            hits.append(hit)
            hits1.append(1.0 if rank == 1 else 0.0)
            rrs.append(rr)
            # nDCG@5 with a single relevant doc: rank<=5 counted, IDCG = 1.
            ndcgs.append((1.0 / math.log2(rank + 1)) if rank is not None else 0.0)

            rel_score = None
            grd_score = None
            if not skip_eval:
                answer_text = synthesize_answer(item["query"], sources)
                context = "\n\n".join(
                    doc.get("parent_content") or doc.get("content", "") for doc in sources
                )
                rel = run_safely(relevance, query=item["query"], response=answer_text)
                grd = run_safely(
                    groundedness, query=item["query"], response=answer_text, context=context
                )
                rel_score = extract_score(rel, "relevance")
                grd_score = extract_score(grd, "groundedness")
                if rel_score is not None:
                    rel_scores.append(rel_score)
                if grd_score is not None:
                    grd_scores.append(grd_score)
                time.sleep(int(os.environ.get("EVAL_DELAY_SECONDS", "2")))

            rows.append(
                {
                    "query": item["query"],
                    "expected_source": item.get("expected_source"),
                    "rank": rank,
                    "sources": [doc["id"] for doc in sources],
                    "relevance": rel_score,
                    "groundedness": grd_score,
                }
            )

        summary[mode] = {
            "hit_rate@5": mean(hits),
            "hit_rate@1": mean(hits1),
            "mrr": mean(rrs),
            "ndcg@5": mean(ndcgs),
            "relevance": mean(rel_scores),
            "groundedness": mean(grd_scores),
            "n": len(rows),
        }
        details[mode] = rows

    out = ROOT / "eval" / "comparison.json"
    out.write_text(json.dumps({"summary": summary, "details": details}, indent=2), encoding="utf-8")

    print(f"{'mode':16}{'hit5':>7}{'hit1':>7}{'mrr':>7}{'ndcg':>7}{'n':>4}")
    for mode in MODES:
        stats = summary[mode]
        print(
            f"{mode:16}{fmt(stats['hit_rate@5']):>7}{fmt(stats['hit_rate@1']):>7}"
            f"{fmt(stats['mrr']):>7}{fmt(stats['ndcg@5']):>7}{stats['n']:>4}"
        )
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
