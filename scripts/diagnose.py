import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from ragpipeline import config


def check(label, func):
    print(f"\n== {label} ==")
    try:
        func()
        print("OK")
    except Exception:
        traceback.print_exc()


print("cwd:", os.getcwd())
print("AZURE_OPENAI_ENDPOINT set:", bool(config.AZURE_OPENAI_ENDPOINT))
print("AZURE_OPENAI_API_KEY set:", bool(config.AZURE_OPENAI_API_KEY))
print("AZURE_OPENAI_API_VERSION:", config.AZURE_OPENAI_API_VERSION)
print("MODEL_DEPLOYMENT_NAME:", config.MODEL_DEPLOYMENT_NAME)
print("EMBEDDING_DEPLOYMENT_NAME:", config.EMBEDDING_DEPLOYMENT_NAME)
print("SEARCH_ENDPOINT set:", bool(config.SEARCH_ENDPOINT))
print("SEARCH_KEY set:", bool(config.SEARCH_KEY))
print("SEARCH_INDEX_NAME:", config.SEARCH_INDEX_NAME)

from ragpipeline.embeddings import embed
check("openai embeddings", lambda: print("embedding dim:", len(embed(["hello"])[0])))

from ragpipeline.index import create_index
check("search create_index", create_index)

from ragpipeline.ingest import build_chunks, load_documents


def show_chunks():
    docs = load_documents()
    chunks = build_chunks(docs)
    print("documents:", len(docs), "chunks:", len(chunks))


check("load + chunk", show_chunks)

from ragpipeline.ingest import ingest
check("full ingest (embed + upload)", lambda: print("uploaded:", ingest()))
