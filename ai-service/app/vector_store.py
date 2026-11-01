from pathlib import Path
import re
import os
import threading
from typing import Optional, List, Dict, Any

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

import chromadb
from chromadb.config import Settings

try:
    from langchain_community.embeddings import HuggingFaceEmbeddings  # type: ignore
except ImportError:
    try:
        from langchain_huggingface import HuggingFaceEmbeddings  # type: ignore
    except ImportError:
        HuggingFaceEmbeddings = None  # type: ignore

from langchain_chroma import Chroma  # type: ignore
from langchain_core.documents import Document  # type: ignore


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


def list_documents(user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Return summary of indexed documents. If user_id given, only that user's docs."""
    try:
        coll = get_collection()
        where_filter = {"user_id": str(user_id)} if user_id is not None else None
        data = (
            coll.get(include=["metadatas"], where=where_filter)
            if where_filter
            else coll.get(include=["metadatas"])
        )
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


def delete_document(filename: str, user_id: Optional[int] = None) -> Dict[str, Any]:
    """Delete all chunks belonging to a specific filename (scoped to user if user_id given)."""
    try:
        coll = get_collection()
        where = {"source": filename}
        if user_id is not None:
            where = {"$and": [{"source": filename}, {"user_id": str(user_id)}]}
        data = coll.get(where=where)
        ids = data.get("ids", []) if data else []
        if ids:
            coll.delete(ids=ids)
            print(f"[VECTOR_STORE] Deleted {len(ids)} chunks for document: '{filename}'")
            return {"success": True, "deleted_chunks": len(ids), "filename": filename}
        return {"success": True, "deleted_chunks": 0, "filename": filename}
    except Exception as e:
        print(f"[VECTOR_STORE] Error deleting document '{filename}': {e}")
        return {"success": False, "deleted_chunks": 0, "filename": filename, "error": str(e)}


def clear_vector_store(user_id: Optional[int] = None) -> int:
    """Clear documents from ChromaDB. If user_id given, only clears that user's docs."""
    try:
        coll = get_collection()
        where_filter = {"user_id": str(user_id)} if user_id is not None else None
        data = coll.get(where=where_filter) if where_filter else coll.get()
        ids = data.get("ids", []) if data else []
        if ids:
            coll.delete(ids=ids)
            print(f"[VECTOR_STORE] Cleared {len(ids)} chunks from ChromaDB.")
            return len(ids)
        return 0
    except Exception as e:
        print(f"[VECTOR_STORE] Note during clearing IDs: {e}")
        return 0


def store_chunks(
    chunks: list,
    filename: str,
    user_id: Optional[int] = None,
    clear_previous: bool = False,
) -> int:
    """
    Store PDF chunks with source + user_id metadata.
    - clear_previous=True: removes ALL of this user's documents first.
    - clear_previous=False (default): only replaces prior version of THIS filename for this user.
    """
    if clear_previous:
        clear_vector_store(user_id=user_id)
    else:
        delete_document(filename, user_id=user_id)

    documents = []
    ids = []
    clean_prefix = re.sub(r"[^a-zA-Z0-9_-]", "_", filename)
    uid_suffix = f"_u{user_id}" if user_id is not None else ""

    for chunk in chunks:
        text = chunk["text"].strip()
        if not text:
            continue

        page_num = int(chunk["page_number"])
        chunk_id = int(chunk["chunk_id"])

        metadata = {
            "source": filename,
            "page_number": page_num,
            "chunk_id": chunk_id,
            "start_index": int(chunk.get("start_index", 0)),
        }
        if user_id is not None:
            metadata["user_id"] = str(user_id)

        documents.append(
            Document(
                page_content=text,
                metadata=metadata,
            )
        )

        ids.append(f"{clean_prefix}{uid_suffix}_p{page_num}_c{chunk_id}")

    if documents:
        vs = get_vector_store()
        vs.add_documents(documents=documents, ids=ids)
        print(f"[VECTOR_STORE] Stored {len(documents)} chunks for '{filename}' (user_id={user_id}).")

    return len(documents)


def search_chunks(
    question: str,
    k: int = 4,
    filter_source: Optional[str] = None,
    user_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Find relevant chunks. Filters by user_id (required for per-user isolation)
    and optionally by specific document.
    """
    try:
        coll = get_collection()

        # Build where filter
        where_conditions = []
        if user_id is not None:
            where_conditions.append({"user_id": str(user_id)})
        if filter_source and filter_source.strip():
            where_conditions.append({"source": filter_source.strip()})

        search_kwargs: Dict[str, Any] = {}
        if len(where_conditions) == 1:
            search_kwargs["filter"] = where_conditions[0]
        elif len(where_conditions) > 1:
            search_kwargs["filter"] = {"$and": where_conditions}

        # Check if there's data to search
        check = coll.get(where=search_kwargs.get("filter")) if search_kwargs.get("filter") else coll.get()
        if not check.get("ids"):
            return []

        vs = get_vector_store()
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
