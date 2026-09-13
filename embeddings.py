"""
Voyage AI embeddings. Chosen over a local sentence-transformer model
specifically for this deployment: Streamlit Community Cloud's free tier
has tight memory limits, and torch + sentence-transformers is heavy
enough to risk the app crashing on deploy. An API call is a few hundred
milliseconds and, at this corpus size, effectively free (200M free
tokens/month vs. a few hundred thousand tokens for your entire corpus).

input_type matters: "document" and "query" use different internal
prompting in Voyage's model and measurably improve retrieval quality
over leaving it blank — always set it correctly.
"""
import voyageai

import config

_client = voyageai.Client(api_key=config.VOYAGE_API_KEY)


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Used at ingest time, for chunk text."""
    result = _client.embed(
        texts, model=config.EMBEDDING_MODEL, input_type="document",
        output_dimension=config.EMBEDDING_DIM,
    )
    return result.embeddings


def embed_query(text: str) -> list[float]:
    """Used at search time, for the user's query text."""
    result = _client.embed(
        [text], model=config.EMBEDDING_MODEL, input_type="query",
        output_dimension=config.EMBEDDING_DIM,
    )
    return result.embeddings[0]
