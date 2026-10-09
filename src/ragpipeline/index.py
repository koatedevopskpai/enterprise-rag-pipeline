from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SearchableField,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)

from ragpipeline.auth import search_credential
from ragpipeline.config import (
    EMBEDDING_DIMENSIONS,
    SEARCH_ENDPOINT,
    SEARCH_INDEX_NAME,
    require,
)


def get_index_client():
    return SearchIndexClient(
        endpoint=require("SEARCH_ENDPOINT", SEARCH_ENDPOINT),
        credential=search_credential(),
    )


def build_index(index_name=SEARCH_INDEX_NAME):
    return SearchIndex(
        name=index_name,
        fields=[
            SimpleField(name="id", type=SearchFieldDataType.String, key=True),
            SimpleField(name="source_id", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="parent_id", type=SearchFieldDataType.String, filterable=True),
            SearchableField(name="section", type=SearchFieldDataType.String),
            SearchableField(name="content", type=SearchFieldDataType.String),
            SimpleField(name="parent_content", type=SearchFieldDataType.String),
            SearchField(
                name="content_vector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=EMBEDDING_DIMENSIONS,
                vector_search_profile_name="hnsw-profile",
            ),
        ],
        vector_search=VectorSearch(
            profiles=[
                VectorSearchProfile(
                    name="hnsw-profile",
                    algorithm_configuration_name="hnsw",
                )
            ],
            algorithms=[HnswAlgorithmConfiguration(name="hnsw")],
        ),
    )


def create_index(index_name=SEARCH_INDEX_NAME):
    client = get_index_client()
    client.create_or_update_index(build_index(index_name))
    return index_name


def reset_index(index_name=SEARCH_INDEX_NAME):
    client = get_index_client()
    try:
        client.delete_index(index_name)
    except Exception:
        pass
    return create_index(index_name)
