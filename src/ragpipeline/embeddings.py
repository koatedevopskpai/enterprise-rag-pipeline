from ragpipeline.auth import openai_client
from ragpipeline.inference_budget import run_inference


def get_openai_client():
    return openai_client()


def embed(texts):
    from ragpipeline.config import EMBEDDING_DEPLOYMENT_NAME

    client = get_openai_client()
    result = run_inference('embedding', client.embeddings.create,
        model=EMBEDDING_DEPLOYMENT_NAME,
        input=texts,
    )
    return [item.embedding for item in result.data]


if __name__ == "__main__":
    vector = embed(["hello world"])[0]
    print("dimensions:", len(vector))
