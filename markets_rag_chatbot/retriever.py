"""
Retrieval layer for finews_bot.

Queries ChromaDB with a user's question and returns the most relevant chunks
to be passed as context to the LLM.
"""

import chromadb
from chromadb.utils import embedding_functions

CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "finews"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
TOP_K = 5


def get_collection():
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)
    return client.get_or_create_collection(name=COLLECTION_NAME, embedding_function=ef)


def retrieve(query: str, top_k: int = TOP_K) -> list[str]:
    """Returns the top_k most relevant text chunks for a given query."""
    collection = get_collection()
    results = collection.query(query_texts=[query], n_results=top_k)
    return results["documents"][0]


def format_context(chunks):
    """Formats retrieved chunks into a single context block for the LLM prompt."""
    return "\n\n---\n\n".join(chunks)

if __name__ == "__main__":
    query = input("Enter your query: ")
    chunks = retrieve(query)

    print(f"Query: {query}\n")
    print("Retrieved context:\n")
    for i, chunk in enumerate(chunks, 1):
        print(f"[{i}] {chunk[:300]}\n")
