# Observability (captured from a live deployment)

Deployed to Azure Container Apps (westus3, scale-to-zero) with Application
Insights. Traces instrument the retrieval and synthesis stages plus the Azure AI
Search and Azure OpenAI calls, all correlated under one request.

## Live metrics (4 `/ask` requests, warm container)

| Span | avg | p50 | p95 |
|---|---|---|---|
| `retrieve` | 766 ms | 722 ms | 888 ms |
| `synthesize` | 1362 ms | 1160 ms | 1712 ms |
| `GET /ask` (end to end) | 2132 ms | 2038 ms | 2423 ms |

The tree per request:

```
GET /ask
├─ retrieve                     (embed query + hybrid search)
│  ├─ POST .../text-embedding-3-large/embeddings
│  └─ POST /indexes('enterprise-docs')/docs/search.post.search
└─ synthesize                   (grounded answer)
   └─ POST .../gpt-4-1-mini/chat/completions
```

Synthesis dominates latency (~64%), driven by the chat completion; retrieval is
~36%, split between the query embedding and the hybrid search.

## Queries

```kusto
// span latencies
dependencies
| where name in ("retrieve", "synthesize")
| summarize avg(duration), percentile(duration, 50), percentile(duration, 95) by name

// end-to-end request latency
requests
| where name == "GET /ask"
| summarize avg(duration), percentile(duration, 50), percentile(duration, 95)

// one request's full call tree
dependencies
| where operation_Id == "<id>"
| project timestamp, name, target, duration
| order by timestamp asc
```

## Evaluation (quality) snapshot

| Metric | Mean |
|---|---|
| relevance | 4.75 |
| groundedness | 5.00 |
| coherence | 4.06 |
| fluency | 3.06 |

Gate (`eval/gate.py`, threshold 3.0): **PASSED**.
