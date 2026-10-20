from pathlib import Path
import re
from typing import Optional, List, Dict, Any

from langchain_community.embeddings import HuggingFaceEmbeddings
# pyrefly: ignore [missing-import]
from langchain_chroma import Chroma
from langchain_core.documents import Document


BASE_DIR = Path(__file__).resolve().parents[1]
DB_DIR = BASE_DIR / "chroma_db"

_embedding_model = None
_vector_store = None


def get_vector_store():
    global _embedding_model, _vector_store

    if _vector_store is None:
        _embedding_model = HuggingFaceEmbeddings(
            model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )

        _vector_store = Chroma(
            collection_name="college_documents",
            embedding_function=_embedding_model,
            persist_directory=str(DB_DIR),
        )

    return _vector_store


def list_documents() -> List[Dict[str, Any]]:
    """Return summary of all currently indexed documents in the vector store."""
    vs = get_vector_store()
    try:
        data = vs.get(include=["metadatas"])
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
    """Delete all chunks belonging to a specific filename."""
    vs = get_vector_store()
    try:
        data = vs.get(where={"source": filename})
        ids = data.get("ids", []) if data else []
        if ids:
            vs.delete(ids=ids)
            print(f"[VECTOR_STORE] Deleted {len(ids)} chunks for document: '{filename}'")
            return {"success": True, "deleted_chunks": len(ids), "filename": filename}
        return {"success": True, "deleted_chunks": 0, "filename": filename}
    except Exception as e:
        print(f"[VECTOR_STORE] Error deleting document '{filename}': {e}")
        return {"success": False, "deleted_chunks": 0, "filename": filename, "error": str(e)}


def clear_vector_store() -> int:
    """Clear all stored documents from ChromaDB."""
    vs = get_vector_store()
    try:
        data = vs.get()
        ids = data.get("ids", []) if data else []
        if ids:
            vs.delete(ids=ids)
            print(f"[VECTOR_STORE] Cleared {len(ids)} chunks from ChromaDB.")
            return len(ids)
    except Exception as e:
        print(f"[VECTOR_STORE] Note during clearing IDs: {e}")
        try:
            vs.reset_collection()
            print("[VECTOR_STORE] Reset collection successfully.")
        except Exception as err:
            print(f"[VECTOR_STORE] Note during reset collection: {err}")
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
        # Replace only existing chunks for this specific document
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
        get_vector_store().add_documents(
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
    vs = get_vector_store()
    try:
        data = vs.get()
        ids = data.get("ids", []) if data else []
        if not ids:
            return []

        search_kwargs = {}
        if filter_source and filter_source.strip():
            search_kwargs["filter"] = {"source": filter_source.strip()}

        results = vs.similarity_search_with_score(question, k=k, **search_kwargs)

        matches = []
        for document, distance in results:
            dist = float(distance)
            # Normalize L2 distance to an approximate 0.0 - 1.0 relevance score
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
