# We built three retrieval modes and they all tied. Here's the harness that proved it.

*Archived draft: the historical tables below are not corroborated by the current
committed comparison report. Do not reuse these headline values in applications
or publication until the matching per-run artifacts are available. See the README
for the numbers currently supported by eval/comparison.json. No new run was made.*

Every RAG tutorial tells you to "use hybrid search" and "add a reranker." Few
show the measurement that justifies either. We built a pluggable retrieval layer
with three strategies and a deterministic benchmark, and the honest result is:
on our corpora, **all three modes tied**.

This is what that looked like, and why it's still useful.

## The three modes

- **vector** — pure embedding similarity over child chunks.
- **hybrid** — keyword (BM25) + vector, fused with reciprocal rank fusion.
- **hybrid_rerank** — hybrid candidates, then an LLM reranks the parent
  sections before synthesis.

All three return deduplicated parent sections with their text and section title.

## The benchmark

Two things make a retrieval benchmark trustworthy:

1. **A deterministic metric.** We measure **hit-rate@5** (was the expected
   source in the top 5?) and **MRR** (mean reciprocal rank of the first correct
   hit). The metric calculation needs no judge. Obtaining retrieval results still
   uses Azure Search and embeddings; the rerank mode calls a model. Deterministic
   scoring does not make the full experiment offline or free.
2. **A hard query set.** Easy questions saturate and tell you nothing. So we
   generated a synthetic corpus: 80 near-duplicate policy documents, each with a
   unique reference code (`REF-9K2MNP`) and limit. Queries ask for exact codes.

## The results

Hit-rate@5:

| Corpus | vector | hybrid | hybrid_rerank |
|---|---|---|---|
| 16 curated docs, 16 Q | 1.00 | 1.00 | 1.00 |
| 80 synthetic docs, code + context | 0.95 | 0.95 | 0.95 |
| 80 synthetic docs, bare codes | 0.95 | 0.95 | 0.95 |

We expected vector to fall over on random tokens. It didn't.

## Why they tied

`text-embedding-3-large` is simply good. Our documents shared almost all their
text, so the only signal distinguishing them — the code — was also the dominant
signal in the embedding differences. Dense retrieval found the needle.

Hybrid can lose recall at a fixed top-k because fusion changes which candidates
survive. The early ties in this draft do not establish a guarantee. Later
semantic and crowded-query comparisons in the README show why ranking quality
and candidate-pool recall need to be assessed separately.

## What this actually means

- **Compare hybrid with vector on the target query set.** Fusion can help or
  hurt at a fixed cutoff. Measure quality, latency and actual service usage.
- **Rerank only when ranking is the bottleneck.** If your hit-rate is high but
  your *top-1* accuracy (or answer quality) is not, a reranker earns its
  latency. If recall is already solved, it's cost with no benefit.
- **Measure on your data.** Retrieval-mode choice is empirical. Our result is
  specific to a small, clean, well-embedded corpus. Your corpus may separate the
  modes sharply — and now you have the harness to find out.

## The takeaway

A negative result you can reproduce beats a cherry-picked win. The deliverable
isn't "hybrid is best" — it's a pluggable retrieval layer plus a deterministic
benchmark and a corpus generator anyone can point at their own data. That's the
difference between a demo and an engineering decision.

> Code: `ragpipeline/strategies.py`, `ragpipeline/rerank.py`,
> `eval/compare_modes.py`, `scripts/generate_eval_corpus.py`.
