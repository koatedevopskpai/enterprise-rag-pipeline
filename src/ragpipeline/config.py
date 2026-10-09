import os
from dotenv import load_dotenv

load_dotenv()

AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21")
MODEL_DEPLOYMENT_NAME = os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-4o-mini")
EMBEDDING_DEPLOYMENT_NAME = os.environ.get("EMBEDDING_DEPLOYMENT_NAME", "text-embedding-3-large")
EMBEDDING_DIMENSIONS = int(os.environ.get("EMBEDDING_DIMENSIONS", "3072"))
SEARCH_ENDPOINT = os.environ.get("SEARCH_ENDPOINT", "")
SEARCH_KEY = os.environ.get("SEARCH_KEY", "")
SEARCH_INDEX_NAME = os.environ.get("SEARCH_INDEX_NAME", "enterprise-docs")
CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", "100"))
RETRIEVE_TOP_K = int(os.environ.get("RETRIEVE_TOP_K", "5"))


def require(name, value):
    if not value:
        raise RuntimeError(f"Missing required setting: {name}. Check your .env file.")
    return value
