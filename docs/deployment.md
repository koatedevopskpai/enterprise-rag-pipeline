# Deployment

The pipeline is exposed as a small FastAPI service (`app/main.py`) and deployed
to Azure Container Apps with Application Insights tracing.

## Endpoints

| Route | Description |
|---|---|
| `GET /health` | liveness + list of retrieval modes |
| `GET /ask?q=<question>&mode=<mode>` | grounded answer with sources |

## Build locally

```powershell
docker build -t enterprise-rag-api .
docker run --env-file .env -p 8000:8000 enterprise-rag-api
# then: curl "http://localhost:8000/ask?q=Which items are not refundable?"
```

## Deploy to Azure Container Apps

The app reuses the AI account + Search service created by
`infra/provision.ps1` (values come from `.env`).

```powershell
az login
powershell -ExecutionPolicy Bypass -File .\infra\provision.ps1 -ResourceGroup rg-ragpipeline-dev3 -WriteEnv
powershell -ExecutionPolicy Bypass -File .\infra\deploy_app.ps1 -ResourceGroup rg-ragpipeline-dev3
```

`deploy_app.ps1`:
1. creates an Application Insights component and reads its connection string,
2. runs `az containerapp up --source .` (builds the Dockerfile in ACR and deploys),
3. sets scaling to **min replicas 0** (scale-to-zero, idle cost ~0).

The command prints the public URL. Verify:

```powershell
curl "https://<fqdn>/health"
curl "https://<fqdn>/ask?q=Which%20items%20are%20not%20refundable"
```

## Observability

`ragpipeline/telemetry.py` calls `configure_azure_monitor` when
`APPLICATIONINSIGHTS_CONNECTION_STRING` is set, and wraps retrieval and
synthesis in spans. FastAPI requests are auto-instrumented. Query traces in
Application Insights:

```kusto
dependencies
| where timestamp > ago(1h)
| where name in ("retrieve", "synthesize")
| project timestamp, name, duration, customDimensions
```

## Authentication

For local dev the app uses API keys. In production, omit the keys and grant the
Container App's managed identity:
- **Cognitive Services OpenAI User** on the AI Services account
- **Search Index Data Reader** on the Search service

The clients fall back to `DefaultAzureCredential` when keys are absent.

## Cost and teardown

See `docs/cost.md`. Container Apps is configured scale-to-zero, so it costs
~$0 while idle; ACR Basic is ~$5/month. Always tear down after a demo:

```powershell
powershell -ExecutionPolicy Bypass -File .\infra\teardown.ps1 -ResourceGroup rg-ragpipeline-dev3
```
