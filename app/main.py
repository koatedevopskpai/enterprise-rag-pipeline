from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query

from ragpipeline.pipeline import DEFAULT_MODE, answer
from ragpipeline.strategies import STRATEGIES
from ragpipeline.telemetry import configure_telemetry


@asynccontextmanager
async def lifespan(app):
    configure_telemetry()
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
    except Exception:
        pass
    yield


app = FastAPI(title="enterprise-rag-pipeline", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "modes": sorted(STRATEGIES)}


@app.get("/ask")
def ask(q: str = Query(..., min_length=1), mode: str = DEFAULT_MODE):
    if mode not in STRATEGIES:
        raise HTTPException(status_code=400, detail=f"unknown mode: {mode}")
    result = answer(q, mode=mode)
    return {
        "answer": result["answer"],
        "mode": result["mode"],
        "sources": [
            {
                "id": doc["id"],
                "source_id": doc.get("source_id"),
                "section": doc.get("section"),
                "score": doc.get("score"),
            }
            for doc in result["sources"]
        ],
    }
