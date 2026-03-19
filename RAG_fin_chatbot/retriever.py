"""
Queries ChromaDB with a user's question and returns all chunks that
exceed a minimum similarity threshold, to be passed as context to the LLM.
"""

import chromadb
from chromadb.utils import embedding_functions

CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "finews"

# using sentence transformer for embeddings distance check 
# lightweight so good fit for small chatbot 
embed_model = "sentence-transformers/all-MiniLM-L6-v2"

# setting threshold for similarity between embeddings for retrieving from DB
similarity_thr = 0.3

def get_collection():
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=embed_model)
    return client.get_or_create_collection(name=COLLECTION_NAME, embedding_function=ef)


def retrieve(query, threshold = similarity_thr):
    """
    Returns all chunks whose cosine similarity
    to the query meets the threshold.
    """
    collection = get_collection()
    n_total = collection.count()
    if n_total == 0:
        return []

    results = collection.query(
        query_texts=[query],
        n_results=n_total,
        include=["documents", "distances"],
    )

    distance_cutoff = 1 - threshold
    filtered = [
        doc
        for doc, dist in zip(results["documents"][0], results["distances"][0])
        if dist <= distance_cutoff
    ]

    print(f"  Retrieved {len(filtered)}/{n_total} chunks above similarity threshold {threshold}.")
    return filtered


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
