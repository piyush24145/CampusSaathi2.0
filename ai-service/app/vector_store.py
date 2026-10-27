from pathlib import Path
import re
import os
import threading
from typing import Optional, List, Dict, Any

import chromadb
from chromadb.config import Settings
import chromadb.utils.embedding_functions as ef


BASE_DIR = Path(__file__).resolve().parents[1]
DB_DIR = BASE_DIR / "chroma_db"

_store_lock = threading.Lock()
_chroma_client = None
_embedding_fn = None


def get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(
            path=str(DB_DIR),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
                is_persistent=True,
            ),
        )
    return _chroma_client


def get_embedding_function():
    global _embedding_fn
    if _embedding_fn is None:
        with _store_lock:
            if _embedding_fn is None:
                # Uses lightweight ONNX runtime (~60MB RAM instead of ~500MB PyTorch)
                _embedding_fn = ef.DefaultEmbeddingFunction()
    return _embedding_fn


def get_collection():
    """Access the persistent Chroma collection with ONNX embedding function."""
    client = get_chroma_client()
    return client.get_or_create_collection(
        name="college_documents",
        embedding_function=get_embedding_function(),
    )


def get_vector_store():
    """Backward compatibility alias."""
    return get_collection()


def list_documents() -> List[Dict[str, Any]]:
    """Return summary of all currently indexed documents in the vector store."""
    try:
        coll = get_collection()
        data = coll.get(include=["metadatas"])
        metadatas = data.get("metadatas", []) if data else []

        doc_map: Dict[str, Dict[str, Any]] = {}
        for meta in metadatas:
            if not meta:
                continue
            source = meta.get("source", "Unknown_Document")
            page_num = meta.get("page_number", 1)

            if source not in doc_map:
                doc_map[source] = {
                    "filename": source,
                    "total_chunks": 0,
                    "pages": set(),
                }

            doc_map[source]["total_chunks"] += 1
            if page_num:
                doc_map[source]["pages"].add(int(page_num))

        docs = []
        for filename, info in doc_map.items():
            sorted_pages = sorted(list(info["pages"]))
            docs.append({
                "filename": filename,
                "total_chunks": info["total_chunks"],
                "pages": sorted_pages,
                "total_pages": len(sorted_pages) if sorted_pages else 1,
            })

        docs.sort(key=lambda d: d["filename"])
        return docs
    except Exception as e:
        print(f"[VECTOR_STORE] Error listing documents: {e}")
        return []


def delete_document(filename: str) -> Dict[str, Any]:
    """Delete all chunks belonging to a specific filename instantly."""
    try:
        coll = get_collection()
        data = coll.get(where={"source": filename})
        ids = data.get("ids", []) if data else []
        if ids:
            coll.delete(ids=ids)
            print(f"[VECTOR_STORE] Deleted {len(ids)} chunks for document: '{filename}'")
            return {"success": True, "deleted_chunks": len(ids), "filename": filename}
        return {"success": True, "deleted_chunks": 0, "filename": filename}
    except Exception as e:
        print(f"[VECTOR_STORE] Error deleting document '{filename}': {e}")
        return {"success": False, "deleted_chunks": 0, "filename": filename, "error": str(e)}


def clear_vector_store() -> int:
    """Clear all stored documents from ChromaDB."""
    try:
        coll = get_collection()
        data = coll.get()
        ids = data.get("ids", []) if data else []
        if ids:
            coll.delete(ids=ids)
            print(f"[VECTOR_STORE] Cleared {len(ids)} chunks from ChromaDB.")
            return len(ids)
        return 0
    except Exception as e:
        print(f"[VECTOR_STORE] Note during clearing IDs: {e}")
        return 0


def store_chunks(chunks: list, filename: str, clear_previous: bool = False) -> int:
    """
    Store PDF chunks with original source metadata.
    Uses native Chroma collection with ONNX embeddings for fast, memory-safe execution on cloud free tiers.
    """
    if clear_previous:
        clear_vector_store()
    else:
        delete_document(filename)

    ids = []
    documents = []
    metadatas = []
    clean_prefix = re.sub(r"[^a-zA-Z0-9_-]", "_", filename)

    for chunk in chunks:
        text = chunk["text"].strip()
        if not text:
            continue

        page_num = int(chunk["page_number"])
        chunk_id = int(chunk["chunk_id"])

        ids.append(f"{clean_prefix}_p{page_num}_c{chunk_id}")
        documents.append(text)
        metadatas.append({
            "source": filename,
            "page_number": page_num,
            "chunk_id": chunk_id,
            "start_index": int(chunk.get("start_index", 0)),
        })

    if documents:
        coll = get_collection()
        # Chroma handles embedding via DefaultEmbeddingFunction (ONNX) in small batches
        batch_size = 64
        for i in range(0, len(documents), batch_size):
            coll.add(
                ids=ids[i:i + batch_size],
                documents=documents[i:i + batch_size],
                metadatas=metadatas[i:i + batch_size],
            )
        print(f"[VECTOR_STORE] Stored {len(documents)} chunks for '{filename}'.")

    return len(documents)


def search_chunks(question: str, k: int = 4, filter_source: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Find relevant chunks across all stored documents or filtered to a single document.
    Returns rich source metadata including snippet and relevance score.
    """
    try:
        coll = get_collection()
        data = coll.get()
        ids = data.get("ids", []) if data else []
        if not ids:
            return []

        where_filter = None
        if filter_source and filter_source.strip():
            where_filter = {"source": filter_source.strip()}

        query_kwargs = {
            "query_texts": [question],
            "n_results": min(k, len(ids)),
        }
        if where_filter:
            query_kwargs["where"] = where_filter

        results = coll.query(**query_kwargs)

        matches = []
        if results and results.get("documents") and results["documents"]:
            docs = results["documents"][0]
            metas = results["metadatas"][0] if results.get("metadatas") and results["metadatas"][0] else [{}] * len(docs)
            distances = results["distances"][0] if results.get("distances") and results["distances"][0] else [0.0] * len(docs)

            for doc_text, meta, dist in zip(docs, metas, distances):
                d = float(dist)
                relevance = max(0.0, min(1.0, round(1.0 / (1.0 + d), 3)))
                matches.append({
                    "text": doc_text,
                    "source": (meta or {}).get("source", "Unknown Document"),
                    "page_number": (meta or {}).get("page_number", 1),
                    "chunk_id": (meta or {}).get("chunk_id", 0),
                    "distance": d,
                    "relevance_score": relevance,
                })

        return matches
    except Exception as e:
        print(f"[VECTOR_STORE] Search error: {e}")
        return []

