# Cost

Historical illustrative estimates; not revalidated prices or a guaranteed cap.
Do not run cloud/model commands under the current GBP 0 portfolio budget.

Approximate, using `gpt-4o-mini`-class pricing and `text-embedding-3-large`.

| Component | Usage | Approx cost |
|---|---|---|
| Embeddings (ingest) | 3 sample docs, ~5 chunks | < $0.01 |
| Embeddings (queries) | per question | negligible |
| Chat (answers) | small prompts, gpt-4.1-mini | < $0.02 per question |
| Azure AI Search | Free tier | $0 |
| Evaluation | 5 golden questions x2 evaluators | < $0.10 |

The table assumes a small example and a particular service configuration.
A local client can still call billable cloud services. Actual charges depend on
the deployed resources, requests, region and pricing at execution time.

## Tags (FinOps)

Every resource is tagged at deployment:

| Tag | Value | Purpose |
|---|---|---|
| project | enterprise-rag-pipeline | cost grouping |
| environment | dev | showback by env |
| owner | koatedevopskpai | accountability |
| costCenter | personal | chargeback |
| managedBy | bicep | drift detection |
| workload | ai-103-portfolio | portfolio-level rollup |
| dataClassification | public | governance |
| expiresOn | today + 30 days | auto-cleanup |

Report costs by tag:
```
Cost Management > Cost analysis > Group by: tag > project
```

## Budget and alerts

Create a subscription budget with `infra/budget.ps1` (default $25/month), then
add 50/80/100% alert thresholds in the portal.

## Cleanup

`infra/cleanup-expired.ps1` deletes resource groups whose `expiresOn` tag is due
(dry run by default; add `-Delete`). Schedule it daily with Task Scheduler to
avoid orphans. Always tear down after a session:

```powershell
powershell -ExecutionPolicy Bypass -File .\infra\teardown.ps1
```

## Deployment (Container Apps)

| Resource | Rate | Idle cost |
|---|---|---|
| Container Apps (0.5 vCPU / 1 GiB) | ~$0.000024/vCPU-s + $0.000003/GiB-s | **$0** with min-replicas 0 |
| Azure Container Registry (Basic) | ~$5/month | ~$0.17/day |
| Application Insights + Log Analytics | ~$2.76/GB ingested | tracing volume tiny (< $0.30) |

`deploy_app.ps1` sets **min-replicas 0**, so the app scales to zero when idle and
costs ~$0 between requests. Same-day deploy + demo + teardown is roughly
**$0.20–1.50**. Leaving ACR + an always-on replica (min-replicas 1) would cost
~$45/month — always run `infra/teardown.ps1` after a demo.
