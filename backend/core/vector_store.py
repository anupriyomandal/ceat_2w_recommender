"""
ChromaDB-backed vector store for tyre recommendations.
Rebuilt in-memory on startup from the Excel data.
Uses OpenAI embeddings (text-embedding-3-small) — no local model download.
"""
import os
import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

from .data_loader import load_tyre_data, records_to_documents

COLLECTION_NAME = "tyre_recommendations"


def build_vector_store(excel_path: str = None) -> tuple:
    """
    Load data and build an in-memory ChromaDB collection.
    Called once at application startup.
    """
    records = load_tyre_data(excel_path)
    documents, metadatas, ids = records_to_documents(records)

    client = chromadb.Client()  # ephemeral / in-memory
    ef = OpenAIEmbeddingFunction(
        api_key=os.environ["OPENAI_API_KEY"],
        model_name="text-embedding-3-small",
    )

    # Drop existing collection if re-initialising
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )

    # Batch upsert (ChromaDB handles lists natively)
    collection.add(documents=documents, metadatas=metadatas, ids=ids)
    return collection, records


def query_collection(
    collection: chromadb.Collection,
    query: str,
    n_results: int = 6,
) -> list[dict]:
    """
    Semantic search over the tyre collection.
    Returns a list of metadata dicts for the top-k matches.
    """
    results = collection.query(
        query_texts=[query],
        n_results=min(n_results, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    hits = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        hits.append({"document": doc, "metadata": meta, "distance": dist})

    return hits
