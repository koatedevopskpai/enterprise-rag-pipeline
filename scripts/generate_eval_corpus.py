import argparse
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TOPICS = [
    "refund", "expense", "travel", "leave", "security", "procurement",
    "retention", "support", "onboarding", "remote", "training", "assets",
]
APPROVERS = ["team manager", "department director", "finance committee", "security officer", "data steward"]
BOILER = "This document describes the {topic} policy for the organisation. " \
         "All employees must follow the requirements described in this document."

# --- semantic (low lexical-overlap paraphrase) corpus -------------------------
CHANNELS = ["email", "portal", "dashboard", "alert", "report"]
CADENCE = ["daily", "weekly", "monthly", "quarterly", "yearly"]
AUDIENCE = ["internal", "customer", "vendor"]

SYN = {
    "email": ["message", "mail", "inbox note", "electronic note"],
    "portal": ["self-service app", "web console", "online panel"],
    "dashboard": ["data view", "overview panel", "scoreboard"],
    "alert": ["notification", "warning feed", "signal"],
    "report": ["briefing", "digest", "summary document"],
    "daily": ["every calendar day", "each morning", "day to day"],
    "weekly": ["every seven days", "each week", "once a week"],
    "monthly": ["every month", "per calendar month"],
    "quarterly": ["every three months", "four times a year"],
    "yearly": ["once per year", "each year"],
    "internal": ["in-house", "staff-facing", "corporate"],
    "customer": ["external clients", "account holders", "buyers"],
    "vendor": ["suppliers", "partner firms", "third parties"],
}

# --- crowded-candidate corpus ------------------------------------------------
COMMON = (
    "The standing review process consolidates submissions, ranks them, and "
    "publishes the result for all responsible parties."
)
KEYWORDS = {
    "courier": ["delivery rider", "rider service", "logistics messenger"],
    "amplify": ["boost", "increase loudness", "magnify"],
    "frost": ["freeze", "cold storage", "sub-zero"],
    "ledger": ["tally", "account record", "balance sheet"],
    "pledge": ["oath", "commitment note", "undertaking"],
    "vault": ["safe room", "secured chamber", "locker"],
    "beacon": ["signal light", "marker", "guide light"],
    "seal": ["lock", "closing strip", "shut band"],
    "anchor": ["mooring point", "holding pin", "fixing point"],
    "cipher": ["code script", "secret key", "encoding mask"],
    "gauge": ["meter reading", "measure dial", "pressure readout"],
    "harbor": ["port basin", "safe berth", "docking area"],
    "igloo": ["ice shelter", "snow dome", "winter hut"],
    "javelin": ["throwing spear", "sport dart", "track lance"],
    "kettle": ["boiling pot", "steam vessel", "heated urn"],
    "lantern": ["hand lamp", "torch holder", "light casing"],
    "mantle": ["covering layer", "cloak sheet", "shield overcoat"],
    "notch": ["slot cut", "bracket mark", "index gap"],
    "opaque": ["non-see-through", "light block", "solid film"],
    "paddle": ["rowing blade", "propulsion board", "sweep oar"],
    "quilt": ["stitched layer", "padding cover", "insulation sheet"],
    "rubble": ["stone debris", "broken fill", "crush heap"],
    "saddle": ["seat mount", "rider perch", "support frame"],
    "toggle": ["switch lever", "flip knob", "catch bar"],
    "urn": ["storage jar", "holding vessel", "receptacle pot"],
    "vane": ["blade fin", "directional sail", "wind needle"],
    "wharf": ["cargo pier", "load dock", "quay edge"],
    "yarn": ["spun strand", "knit thread", "weave fiber"],
    "zinc": ["metal plate", "alloy sheet", "galvanic coat"],
    "aperture": ["opening slit", "camera hole", "light gap"],
    "brew": ["steeped mix", "hot infusion", "liquid batch"],
    "chime": ["tone bell", "ring signal", "sound ping"],
    "dune": ["sand ridge", "sediment swell", "wind mound"],
    "ember": ["glowing coal", "heat remnant", "burning cinder"],
    "finch": ["songbird", "small bird", "passerine"],
    "grove": ["tree cluster", "wooded stand", "orchard patch"],
    "herb": ["aromatic plant", "leaf spice", "garden leaf"],
    "inlet": ["water gap", "bay mouth", "coastal cut"],
    "jewel": ["gem stone", "ornament rock", "precious facet"],
    "kelp": ["seaweed strand", "algae rope", "ocean plant"],
    "lodge": ["timber cabin", "mountain hut", "stay house"],
    "moss": ["green cover", "soft carpet", "moist layer"],
    "nutmeg": ["spiced kernel", "aromatic seed", "warm spice"],
    "oyster": ["shellfish", "saltwater mollusc", "pearl bearer"],
    "plume": ["feather tuft", "smoke trail", "rise column"],
}
ADJ = ["amplified", "sealed", "frost-protected", "triple-signed", "morning", "month-end"]


def make_code(rng):
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ0123456789"
    return "REF-" + "".join(rng.choice(alphabet) for _ in range(6))


def build_policy(idx, topic, ref, limit, approver):
    return f"""# {topic.title()} Policy ({idx:03d})

{BOILER.format(topic=topic)}

## Reference

The reference code for this policy is {ref}. The maximum permitted value is {limit} units.

## Scope

This policy applies to all {topic}-related activities and supersedes any earlier
guidance on the same subject. It should be read together with the general handbook.

## Approvals

Changes to this policy require approval by the {approver} and are reviewed annually.
"""


def build_semantic(idx, channel, cadence, audience):
    return f"""# {channel.title()} Policy ({idx:03d})

Generic distribution policy. This publishes a {channel} {cadence} update for the
{audience} audience.

## Distribution

The {channel} update is {cadence} and targeted at the {audience} group.

## Notes

Nothing else in this policy is material to retrieval experiments.
"""


def build_crowded(idx, keyword):
    return f"""# Submission Review ({idx:03d})

{COMMON}

## Special note

Only one file references the {keyword} requirement.

## Metadata

Index {idx}; most content below is shared boilerplate used to crowd the ranking.
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", choices=["codes", "semantic", "crowded"], default="codes")
    parser.add_argument("--docs", type=int, default=40)
    parser.add_argument("--queries", type=int, default=20)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    rng = random.Random(args.seed)

    if args.corpus == "codes":
        docs_dir = ROOT / "data" / "generated"
        golden = ROOT / "eval" / "golden_set_large.jsonl"
        docs_dir.mkdir(parents=True, exist_ok=True)
        for existing in docs_dir.glob("*.md"):
            existing.unlink()

        records = []
        for idx in range(args.docs):
            topic = rng.choice(TOPICS)
            ref = make_code(rng)
            limit = rng.randint(50, 5000)
            approver = rng.choice(APPROVERS)
            stem = f"gen_{idx:03d}"
            (docs_dir / f"{stem}.md").write_text(build_policy(idx, topic, ref, limit, approver), "utf-8")
            records.append({"source": stem, "topic": topic, "ref": ref, "limit": limit, "approver": approver})

        rng.shuffle(records)
        lines = []
        for rec in records[: args.queries]:
            lines.append(json.dumps({"query": rec["ref"], "expected_source": rec["source"], "type": "exact_code_bare"}))
            lines.append(json.dumps({"query": f"Which policy has reference code {rec['ref']}?", "expected_source": rec["source"], "type": "exact_code_context"}))
            lines.append(json.dumps({"query": f"Which policy sets a maximum permitted value of {rec['limit']} units?", "expected_source": rec["source"], "type": "paraphrase_limit"}))
            lines.append(json.dumps({"query": f"Which policy about {rec['topic']} requires approval by the {rec['approver']}?", "expected_source": rec["source"], "type": "ambiguous_topic"}))
        golden.write_text("\n".join(lines) + "\n", "utf-8")
        print(f"codes: {args.docs} docs -> {docs_dir}; {len(lines)} queries -> {golden}")

    elif args.corpus == "semantic":
        docs_dir = ROOT / "data" / "generated_semantic"
        golden = ROOT / "eval" / "golden_set_semantic.jsonl"
        docs_dir.mkdir(parents=True, exist_ok=True)
        for existing in docs_dir.glob("*.md"):
            existing.unlink()

        combos = [(c, cd, a) for c in CHANNELS for cd in CADENCE for a in AUDIENCE]
        rng.shuffle(combos)
        chosen = combos[: args.docs]

        records = []
        for idx, (channel, cadence, audience) in enumerate(chosen):
            stem = f"sem_{idx:03d}"
            (docs_dir / f"{stem}.md").write_text(build_semantic(idx, channel, cadence, audience), "utf-8")
            records.append({"source": stem, "channel": channel, "cadence": cadence, "audience": audience})

        rng.shuffle(records)
        lines = []
        for rec in records[: args.queries]:
            ch = rng.choice(SYN[rec["channel"]])
            cd = rng.choice(SYN[rec["cadence"]])
            au = rng.choice(SYN[rec["audience"]])
            query = f"Which policy delivers a {ch} for the {au} teams {cd}?"
            lines.append(json.dumps({
                "query": query,
                "expected_source": rec["source"],
                "type": "semantic_low_overlap",
            }))
        golden.write_text("\n".join(lines) + "\n", "utf-8")
        print(f"semantic: {args.docs} docs -> {docs_dir}; {len(lines)} queries -> {golden}")

    else:  # crowded
        docs_dir = ROOT / "data" / "generated_crowded"
        golden = ROOT / "eval" / "golden_set_crowded.jsonl"
        docs_dir.mkdir(parents=True, exist_ok=True)
        for existing in docs_dir.glob("*.md"):
            existing.unlink()

        keywords = list(KEYWORDS.keys())
        rng.shuffle(keywords)
        chosen = keywords[: args.docs]

        records = []
        for idx, keyword in enumerate(chosen):
            stem = f"crowd_{idx:03d}"
            (docs_dir / f"{stem}.md").write_text(build_crowded(idx, keyword), "utf-8")
            records.append({"source": stem, "keyword": keyword})

        rng.shuffle(records)
        lines = []
        for rec in records[: args.queries]:
            syn = rng.choice(KEYWORDS[rec["keyword"]])
            lines.append(json.dumps({
                "query": f"Which submission mentions {syn} handling in the standing review?",
                "expected_source": rec["source"],
                "type": "crowded_near_equal",
            }))
        golden.write_text("\n".join(lines) + "\n", "utf-8")
        print(f"crowded: {args.docs} docs -> {docs_dir}; {len(lines)} queries -> {golden}")


if __name__ == "__main__":
    main()