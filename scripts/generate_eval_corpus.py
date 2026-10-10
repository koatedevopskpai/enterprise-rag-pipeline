import argparse
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "data" / "generated"
GOLDEN = ROOT / "eval" / "golden_set_large.jsonl"

TOPICS = [
    "refund", "expense", "travel", "leave", "security", "procurement",
    "retention", "support", "onboarding", "remote", "training", "assets",
]

APPROVERS = ["team manager", "department director", "finance committee", "security officer", "data steward"]

BOILER = (
    "This document describes the {topic} policy for the organisation. "
    "All employees must follow the requirements described in this document."
)


def make_code(rng):
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ0123456789"
    return "REF-" + "".join(rng.choice(alphabet) for _ in range(6))


def make_doc(index, topic, ref, limit, approver):
    return f"""# {topic.title()} Policy ({index:03d})

{BOILER.format(topic=topic)}

## Reference

The reference code for this policy is {ref}. The maximum permitted value is {limit} units.

## Scope

This policy applies to all {topic}-related activities and supersedes any earlier
guidance on the same subject. It should be read together with the general
handbook.

## Approvals

Changes to this policy require approval by the {approver} and are reviewed
annually.
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--docs", type=int, default=80)
    parser.add_argument("--queries", type=int, default=20)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    for existing in DOCS_DIR.glob("*.md"):
        existing.unlink()

    records = []
    for index in range(args.docs):
        topic = rng.choice(TOPICS)
        ref = make_code(rng)
        limit = rng.randint(50, 5000)
        approver = rng.choice(APPROVERS)
        stem = f"gen_{index:03d}"
        (DOCS_DIR / f"{stem}.md").write_text(
            make_doc(index, topic, ref, limit, approver), encoding="utf-8"
        )
        records.append(
            {
                "source": stem,
                "topic": topic,
                "ref": ref,
                "limit": limit,
                "approver": approver,
            }
        )

    rng.shuffle(records)
    chosen = records[: args.queries]

    lines = []
    for record in chosen:
        lines.append(
            json.dumps(
                {
                    "query": record["ref"],
                    "expected_source": record["source"],
                    "type": "exact_code_bare",
                }
            )
        )
        lines.append(
            json.dumps(
                {
                    "query": f"Which policy has reference code {record['ref']}?",
                    "expected_source": record["source"],
                    "type": "exact_code_context",
                }
            )
        )
        lines.append(
            json.dumps(
                {
                    "query": f"Which policy sets a maximum permitted value of {record['limit']} units?",
                    "expected_source": record["source"],
                    "type": "paraphrase_limit",
                }
            )
        )
        lines.append(
            json.dumps(
                {
                    "query": f"Which policy about {record['topic']} requires approval by the {record['approver']}?",
                    "expected_source": record["source"],
                    "type": "ambiguous_topic",
                }
            )
        )

    GOLDEN.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {args.docs} docs to {DOCS_DIR}")
    print(f"wrote {len(lines)} queries to {GOLDEN}")


if __name__ == "__main__":
    main()
