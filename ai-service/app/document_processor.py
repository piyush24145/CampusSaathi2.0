
import gc
import fitz


def split_text_recursive(text: str, chunk_size: int = 700, chunk_overlap: int = 60) -> list:
    """
    Ultra-lightweight pure-Python recursive text splitter.
    Splits text cleanly along natural paragraph, sentence, and word boundaries
    without loading heavy 480MB LangChain packages into RAM.
    """
    if not text or not text.strip():
        return []

    separators = ["\n\n", "\n", ". ", "? ", "! ", " "]

    def _split(s: str, seps: list) -> list:
        s = s.strip()
        if not seps or len(s) <= chunk_size:
            return [s] if s else []

        sep = seps[0]
        parts = s.split(sep)
        chunks = []
        curr = ""

        for part in parts:
            cand = f"{curr}{sep}{part}" if curr else part
            if len(cand) <= chunk_size:
                curr = cand
            else:
                if curr and curr.strip():
                    chunks.append(curr.strip())
                if len(part) > chunk_size:
                    chunks.extend(_split(part, seps[1:]))
                    curr = ""
                else:
                    curr = part

        if curr and curr.strip():
            chunks.append(curr.strip())

        return chunks

    raw_chunks = [c for c in _split(text, separators) if c]

    # Add overlapping context if multiple chunks exist
    if chunk_overlap > 0 and len(raw_chunks) > 1:
        final_chunks = [raw_chunks[0]]
        for c in raw_chunks[1:]:
            prev_tail = final_chunks[-1][-chunk_overlap:]
            final_chunks.append(f"...{prev_tail} {c}")
        return final_chunks

    return raw_chunks


def extract_text_from_pdf(pdf_bytes: bytes, max_pages: int = 35) -> dict:
    """
    Extract text from each PDF page and preserve page numbers.
    Caps max pages to 35 to protect low-RAM server instances.
    """
    pages = []
    total_doc_pages = 0

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        total_doc_pages = len(doc)
        limit = min(total_doc_pages, max_pages)

        for page_index in range(limit):
            page = doc.load_page(page_index)
            text = page.get_text("text").strip()

            if text:
                pages.append({
                    "page_number": page_index + 1,
                    "text": text
                })
    finally:
        doc.close()
        gc.collect()

    return {
        "total_pages": total_doc_pages,
        "processed_pages": len(pages),
        "pages": pages
    }


def split_pages_into_chunks(pages: list) -> list:
    """
    Split page text into smaller chunks while retaining source pages.
    """
    chunks = []

    for page in pages:
        page_chunks = split_text_recursive(page["text"], chunk_size=700, chunk_overlap=60)

        for text_chunk in page_chunks:
            chunks.append({
                "chunk_id": len(chunks) + 1,
                "page_number": page["page_number"],
                "text": text_chunk,
                "start_index": 0
            })

    return chunks

