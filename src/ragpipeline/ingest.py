from pathlib import Path

from azure.search.documents import SearchIndexingBufferedSender

from ragpipeline.auth import search_credential
from ragpipeline.chunking import chunk_markdown
from ragpipeline.config import SEARCH_ENDPOINT, SEARCH_INDEX_NAME, require
from ragpipeline.embeddings import embed

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "sample_docs"


def load_documents(data_dir=DEFAULT_DATA_DIR):
    documents = []
    for path in sorted(Path(data_dir).glob("*.md")):
        documents.append({"source_id": path.stem, "content": path.read_text(encoding="utf-8")})
    return documents


def build_chunks(documents):
    chunks = []
    for doc in documents:
        chunks.extend(chunk_markdown(doc["content"], doc["source_id"]))
    return chunks


def upload_chunks(chunks, index_name=SEARCH_INDEX_NAME):
    vectors = embed([chunk["content"] for chunk in chunks])
    for chunk, vector in zip(chunks, vectors):
        chunk["content_vector"] = vector

    with SearchIndexingBufferedSender(
        endpoint=require("SEARCH_ENDPOINT", SEARCH_ENDPOINT),
        index_name=index_name,
        credential=search_credential(),
    ) as client:
        client.upload_documents(documents=chunks)
    return len(chunks)


def ingest(data_dir=DEFAULT_DATA_DIR, index_name=SEARCH_INDEX_NAME):
    chunks = build_chunks(load_documents(data_dir))
    upload_chunks(chunks, index_name=index_name)
    return len(chunks)
