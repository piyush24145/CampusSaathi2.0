from pathlib import Path
import re
import os
import threading
from typing import Optional, List, Dict, Any

import chromadb
from chromadb.config import Settings
from langchain_community.embeddings import HuggingFaceEmbeddings
# pyrefly: ignore [missing-import]
from langchain_chroma import Chroma
from langchain_core.documents import Document


BASE_DIR = Path(__file__).resolve().parents[1]
DB_DIR = BASE_DIR / "chroma_db"

_store_lock = threading.Lock()
_embedding_model = None
_vector_store = None
_chroma_client = None


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


def get_collection():
    """Direct fast access to Chroma collection for metadata queries without loading embedding model."""
    client = get_chroma_client()
    return client.get_or_create_collection(name="college_documents")


def get_vector_store():
    global _embedding_model, _vector_store

    if _vector_store is not None:
        return _vector_store

    with _store_lock:
        if _vector_store is not None:
            return _vector_store

        try:
            if _embedding_model is None:
                model_name = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
                _embedding_model = HuggingFaceEmbeddings(model_name=model_name)

            client = get_chroma_client()
            _vector_store = Chroma(
                client=client,
                collection_name="college_documents",
                embedding_function=_embedding_model,
            )
            return _vector_store
        except Exception as e:
            print(f"[VECTOR_STORE] Error creating Chroma vector store: {e}")
            _vector_store = None
            raise


def list_documents() -> List[Dict[str, Any]]:
    """Return summary of all currently indexed documents in the vector store instantly without embedding overhead."""
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
    """Delete all chunks belonging to a specific filename instantly via direct collection."""
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
    If clear_previous is True, all existing docs are removed.
    If clear_previous is False (default), only any prior version of THIS specific filename is replaced,
    preserving all other uploaded documents!
    """
    if clear_previous:
        clear_vector_store()
    else:
        delete_document(filename)

    documents = []
    ids = []
    clean_prefix = re.sub(r"[^a-zA-Z0-9_-]", "_", filename)

    for chunk in chunks:
        text = chunk["text"].strip()
        if not text:
            continue

        page_num = int(chunk["page_number"])
        chunk_id = int(chunk["chunk_id"])

        documents.append(
            Document(
                page_content=text,
                metadata={
                    "source": filename,
                    "page_number": page_num,
                    "chunk_id": chunk_id,
                    "start_index": int(chunk.get("start_index", 0)),
                },
            )
        )

        ids.append(f"{clean_prefix}_p{page_num}_c{chunk_id}")

    if documents:
        vs = get_vector_store()
        vs.add_documents(
            documents=documents,
            ids=ids,
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
        ids = coll.get().get("ids", [])
        if not ids:
            return []

        vs = get_vector_store()
        search_kwargs = {}
        if filter_source and filter_source.strip():
            search_kwargs["filter"] = {"source": filter_source.strip()}

        results = vs.similarity_search_with_score(question, k=k, **search_kwargs)

        matches = []
        for document, distance in results:
            dist = float(distance)
            relevance = max(0.0, min(1.0, round(1.0 / (1.0 + dist), 3)))

            matches.append({
                "text": document.page_content,
                "source": document.metadata.get("source", "Unknown Document"),
                "page_number": document.metadata.get("page_number", 1),
                "chunk_id": document.metadata.get("chunk_id", 0),
                "distance": dist,
                "relevance_score": relevance,
            })

        return matches
    except Exception as e:
        print(f"[VECTOR_STORE] Search error: {e}")
        return []
