import os
from app.document_processor import extract_text_from_pdf, split_pages_into_chunks
from app.vector_store import store_chunks, list_documents, search_chunks, clear_vector_store

SAMPLE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sample_college_notices")

print("--- Testing Vector Store and Multi-Document Support ---")
clear_vector_store()

# Upload Document 1: Exam Schedule
exam_pdf = os.path.join(SAMPLE_DIR, "Notice_Exam_Schedule_2026.pdf")
with open(exam_pdf, "rb") as f:
    res1 = extract_text_from_pdf(f.read())
chunks1 = split_pages_into_chunks(res1["pages"])
c1_stored = store_chunks(chunks1, "Notice_Exam_Schedule_2026.pdf", clear_previous=False)
print(f"Uploaded Notice_Exam_Schedule_2026.pdf: {c1_stored} chunks")

# Upload Document 2: Hostel Rules
hostel_pdf = os.path.join(SAMPLE_DIR, "Notice_Hostel_Allotment_Rules_2026.pdf")
with open(hostel_pdf, "rb") as f:
    res2 = extract_text_from_pdf(f.read())
chunks2 = split_pages_into_chunks(res2["pages"])
c2_stored = store_chunks(chunks2, "Notice_Hostel_Allotment_Rules_2026.pdf", clear_previous=False)
print(f"Uploaded Notice_Hostel_Allotment_Rules_2026.pdf: {c2_stored} chunks")

# Upload Document 3: Library Rules
lib_pdf = os.path.join(SAMPLE_DIR, "Notice_Library_Guidelines_Timings.pdf")
with open(lib_pdf, "rb") as f:
    res3 = extract_text_from_pdf(f.read())
chunks3 = split_pages_into_chunks(res3["pages"])
c3_stored = store_chunks(chunks3, "Notice_Library_Guidelines_Timings.pdf", clear_previous=False)
print(f"Uploaded Notice_Library_Guidelines_Timings.pdf: {c3_stored} chunks")

# Verify list_documents
docs = list_documents()
print(f"\nTotal documents in system: {len(docs)}")
for d in docs:
    print(f" - {d['filename']} (pages: {d['pages']}, chunks: {d['total_chunks']})")

assert len(docs) == 3, f"Expected 3 documents, got {len(docs)}"

# Test Query 1: Exam specific
q1 = "When do the semester examinations start and what is the fee?"
m1 = search_chunks(q1, k=2)
print(f"\nQuery: '{q1}'")
for m in m1:
    print(f" -> Source: {m['source']}, Page: {m['page_number']}, Score: {m['relevance_score']}")
assert any("Exam_Schedule" in m["source"] for m in m1), "Exam chunk should be top match"

# Test Query 2: Hostel specific
q2 = "What is the curfew time for hostel residents?"
m2 = search_chunks(q2, k=2)
print(f"\nQuery: '{q2}'")
for m in m2:
    print(f" -> Source: {m['source']}, Page: {m['page_number']}, Score: {m['relevance_score']}")
assert any("Hostel" in m["source"] for m in m2), "Hostel chunk should be top match"

# Test Query 3: Library specific
q3 = "How many books can a B.Tech student borrow and what is the fine?"
m3 = search_chunks(q3, k=2)
print(f"\nQuery: '{q3}'")
for m in m3:
    print(f" -> Source: {m['source']}, Page: {m['page_number']}, Score: {m['relevance_score']}")
assert any("Library" in m["source"] for m in m3), "Library chunk should be top match"

print("\n--- ALL MULTI-DOCUMENT VECTOR STORE TESTS PASSED ---")
