"""
rag_service.py
--------------
RAG (Retrieval-Augmented Generation) pipeline for CampusSathi.

Responsibilities:
  - Retrieve relevant document chunks from ChromaDB
  - Build grounded prompt context from multiple documents
  - Call Gnani Evon (gnani/gnani-evon-v3.3-30B-A3B) via Hugging Face
  - Return structured answer + citations
"""

import asyncio
import os
from typing import Optional, List, Dict, Any

from fastapi import HTTPException

from app.vector_store import search_chunks, list_documents
from app.llm import generate_chat_completion


# ---------------------------------------------------------------------------
# Not-found indicator phrases (to detect unanswerable responses)
# ---------------------------------------------------------------------------
NOT_FOUND_INDICATORS = [
    "nahi mili",
    "uplabdh nahi",
    "not found in the uploaded",
    "not mentioned in the uploaded",
    "not available in the uploaded",
    "not in the provided",
    "document me nahi",
    "documents me nahi",
    "not mentioned in the document",
    "cannot be answered from the provided",
    "no information regarding",
    "koi jaankari nahi",
    "not available in the provided",
    "not mentioned in any of the",
]


def _is_unanswerable(answer: str) -> bool:
    """Return True if the LLM answer signals it could not find info in docs."""
    lower = answer.lower()
    return any(phrase in lower for phrase in NOT_FOUND_INDICATORS)


def _build_context(matches: List[Dict[str, Any]]) -> str:
    """Format retrieved chunks into a numbered multi-document context block."""
    parts = []
    for idx, item in enumerate(matches, 1):
        src = item.get("source", "Unknown Document")
        page = item.get("page_number", 1)
        text = item.get("text", "")
        parts.append(f"[DOCUMENT {idx}: {src} | Page: {page}]\n{text}")
    return "\n\n".join(parts)


def _build_system_prompt(doc_list_str: str) -> str:
    """Build the strict-grounding system prompt for Gnani Evon."""
    return (
        "You are CampusSathi AI, an intelligent, reliable college student assistant powered by Gnani AI.\n"
        f"Active Uploaded Documents in System: {doc_list_str}\n\n"
        "CRITICAL INSTRUCTIONS FOR ACCURACY & RELIABILITY:\n"
        "1. STRICT GROUNDING: Answer strictly using ONLY the information provided in the "
        "Document Context Excerpts. Never invent, extrapolate, or assume facts not explicitly mentioned.\n"
        "2. CITATIONS: Whenever stating a fact, date, fee, timing, or rule, explicitly attribute "
        "the statement to its specific document name and page number "
        "(e.g. `[Notice_Exam_Schedule_2026.pdf, Page 1]`).\n"
        "3. MULTIPLE DOCUMENTS: The context may contain excerpts from several distinct college notices. "
        "Keep details from different documents separate. Never confuse hostel rules with exam rules or library timings.\n"
        "4. UNANSWERABLE & OUT-OF-DOMAIN QUESTIONS:\n"
        "   - If the student's question CANNOT be answered from the provided document context, "
        "you MUST clearly and politely state:\n"
        "     'Yeh jaankari uploaded documents me nahi mili. / "
        "This information is not found in the uploaded documents.'\n"
        "   - Briefly inform the student what notices are currently available. Never guess or hallucinate.\n"
        "5. TONE & LANGUAGE: Clear, student-friendly, and concise. "
        "Respond in the language used by the user (Hindi, Hinglish, or English)."
    )


def _format_sources(matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate and format source citations from retrieved chunks."""
    sources = []
    seen = set()
    for item in matches:
        key = (item.get("source"), item.get("page_number"), item.get("chunk_id"))
        if key in seen:
            continue
        seen.add(key)
        txt = item.get("text", "").strip()
        sources.append({
            "source": item.get("source"),
            "page_number": item.get("page_number"),
            "chunk_id": item.get("chunk_id"),
            "snippet": txt[:260] + ("..." if len(txt) > 260 else ""),
            "relevance_score": item.get("relevance_score", 0.0),
        })
    return sources


# ---------------------------------------------------------------------------
# Main RAG function
# ---------------------------------------------------------------------------

async def answer_question(
    question: str,
    k: int = 4,
    filter_source: Optional[str] = None,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Full RAG pipeline powered by Gnani Evon:
      1. Check if any documents are available.
      2. Retrieve top-k relevant chunks from vector store.
      3. Build context + system prompt.
      4. Call Gnani Evon (Hugging Face / vLLM).
      5. Return structured response with citations.

    Raises HTTPException on configuration or generation errors.
    """
    hf_token = (
        os.getenv("HUGGINGFACE_API_KEY")
        or os.getenv("HF_TOKEN")
        or ""
    ).strip()
    evon_key = (os.getenv("GNANI_EVON_KEY") or "").strip()
    evon_endpoint = (os.getenv("GNANI_EVON_ENDPOINT") or "").strip()

    if not hf_token and not evon_key and not evon_endpoint:
        raise HTTPException(
            status_code=500,
            detail=(
                "Gnani Evon credentials missing. "
                "Please configure GNANI_EVON_KEY or HUGGINGFACE_API_KEY in ai-service/.env."
            ),
        )

    # Step 1: Guard — no documents uploaded yet
    current_docs = list_documents(user_id=user_id)
    if not current_docs:
        return {
            "success": True,
            "question": question,
            "answer": (
                "Abhi tak koi bhi college document ya notice upload nahi kiya gaya hai. "
                "Kripya pehle notice (PDF) upload karein, phir sawaal poochein! / "
                "No college notices have been uploaded yet. Please upload a PDF notice first."
            ),
            "sources": [],
            "is_answerable": False,
            "documents_available": [],
        }

    try:
        # Step 2: Retrieve relevant chunks
        matches = await asyncio.to_thread(
            search_chunks, question, k=k, filter_source=filter_source, user_id=user_id
        )

        if not matches:
            doc_names = ", ".join(d["filename"] for d in current_docs)
            return {
                "success": True,
                "question": question,
                "answer": (
                    f"Yeh jaankari uploaded documents ({doc_names}) me nahi mili. "
                    "Aap exam dates, fees, ya rules ke baare me pooch sakte hain."
                ),
                "sources": [],
                "is_answerable": False,
                "documents_available": [d["filename"] for d in current_docs],
            }

        # Step 3: Build context + prompt
        context = _build_context(matches)
        doc_names_list = [d["filename"] for d in current_docs]
        system_prompt = _build_system_prompt(", ".join(doc_names_list))

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Question: {question}\n\nDocument Context Excerpts:\n{context}",
            },
        ]

        # Step 4: Call Gnani Evon
        answer, model_used = await asyncio.to_thread(
            generate_chat_completion, messages, hf_token
        )

        if not answer:
            raise RuntimeError("Gnani Evon returned an empty answer.")

        # Step 5: Build response
        unanswerable = _is_unanswerable(answer)
        sources = [] if unanswerable else _format_sources(matches)

        return {
            "success": True,
            "question": question,
            "answer": answer,
            "model_used": model_used,
            "is_answerable": not unanswerable,
            "sources": sources,
            "documents_available": doc_names_list,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=(
                f"Could not generate an answer with Gnani Evon: {str(e)}. "
                "Check your Hugging Face API key, model availability, and network connection."
            ),
        )
