import os
from pathlib import Path
from typing import Dict, Any

from app.document_processor import extract_text_from_pdf, split_pages_into_chunks
from app.vector_store import store_chunks, list_documents


def seed_sample_notices_if_empty() -> Dict[str, Any]:
    """
    Auto-seeds sample college notices into ChromaDB if the database is currently empty.
    This guarantees that on Google Cloud Run deployment (fresh container start),
    the assistant immediately has notices available and answers student questions out-of-the-box.
    """
    try:
        current_docs = list_documents()
        if current_docs and len(current_docs) > 0:
            print(f"[SEEDER] Vector store already contains {len(current_docs)} document(s). Skipping seed.")
            return {"status": "skipped", "reason": "already_populated", "count": len(current_docs)}

        # Search candidates for sample notices directory
        base_dir = Path(__file__).resolve().parents[1]
        candidates = [
            base_dir / "sample_college_notices",
            base_dir.parent / "data" / "sample_college_notices",
            Path("/app/sample_college_notices"),
            Path("/app/data/sample_college_notices"),
        ]

        sample_dir = None
        for cand in candidates:
            if cand.exists() and cand.is_dir():
                sample_dir = cand
                break

        if not sample_dir:
            print("[SEEDER] Notice directory not found in candidates, skipping auto-seed.")
            return {"status": "skipped", "reason": "directory_not_found"}

        pdf_files = sorted(list(sample_dir.glob("*.pdf")))
        if not pdf_files:
            print(f"[SEEDER] No PDF files found in {sample_dir}.")
            return {"status": "skipped", "reason": "no_pdfs_found"}

        print(f"[SEEDER] Auto-seeding {len(pdf_files)} college notices from: {sample_dir}")
        total_chunks = 0
        seeded_docs = []

        for pdf_path in pdf_files:
            try:
                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()

                extracted = extract_text_from_pdf(pdf_bytes)
                if extracted.get("pages"):
                    chunks = split_pages_into_chunks(extracted["pages"])
                    stored = store_chunks(chunks, pdf_path.name, clear_previous=False)
                    total_chunks += stored
                    seeded_docs.append(pdf_path.name)
                    print(f"[SEEDER] Indexed '{pdf_path.name}' ({stored} chunks)")
            except Exception as doc_err:
                print(f"[SEEDER] Could not index {pdf_path.name}: {doc_err}")

        print(f"[SEEDER] Successfully seeded {len(seeded_docs)} notices ({total_chunks} total chunks).")
        return {
            "status": "seeded",
            "documents_seeded": seeded_docs,
            "total_chunks": total_chunks,
        }

    except Exception as e:
        print(f"[SEEDER ERROR] Failed auto-seeding sample notices: {e}")
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    result = seed_sample_notices_if_empty()
    print("Seed result:", result)
