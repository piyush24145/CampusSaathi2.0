
try:
    import pymupdf as fitz
except ImportError:
    import fitz
from langchain_text_splitters import RecursiveCharacterTextSplitter


def extract_text_from_pdf(pdf_bytes: bytes) -> dict:
    """Extract text from each PDF page and preserve page numbers."""

    pages = []

    with fitz.open(stream=pdf_bytes, filetype="pdf") as pdf:
        for page_index, page in enumerate(pdf):
            text = page.get_text("text").strip()

            if text:
                pages.append({
                    "page_number": page_index + 1,
                    "text": text
                })

    return {
        "total_pages": len(pages),
        "pages": pages
    }


def split_pages_into_chunks(pages: list) -> list:
    """Split page text into smaller chunks while retaining source pages."""

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=80,
        add_start_index=True
    )

    chunks = []

    for page in pages:
        page_chunks = splitter.create_documents(
            texts=[page["text"]]
        )

        for chunk in page_chunks:
            chunks.append({
                "chunk_id": len(chunks) + 1,
                "page_number": page["page_number"],
                "text": chunk.page_content,
                "start_index": chunk.metadata.get("start_index", 0)
            })

    return chunks
