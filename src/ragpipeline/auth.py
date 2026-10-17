from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

from ragpipeline.config import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_ENDPOINT,
    SEARCH_KEY,
    require,
)

TOKEN_SCOPE = "https://cognitiveservices.azure.com/.default"


def openai_client():
    endpoint = require("AZURE_OPENAI_ENDPOINT", AZURE_OPENAI_ENDPOINT)
    if AZURE_OPENAI_API_KEY:
        return AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_OPENAI_API_VERSION,
            max_retries=0,
            timeout=30,
        )
    token_provider = get_bearer_token_provider(DefaultAzureCredential(), TOKEN_SCOPE)
    return AzureOpenAI(
        azure_endpoint=endpoint,
        azure_ad_token_provider=token_provider,
        api_version=AZURE_OPENAI_API_VERSION,
        max_retries=0,
        timeout=30,
    )


def search_credential():
    if SEARCH_KEY:
        return AzureKeyCredential(SEARCH_KEY)
    return DefaultAzureCredential()
