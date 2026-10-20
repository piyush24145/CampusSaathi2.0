import os
from app.main import ask_question, AskRequest

print("--- Testing RAG Answer Reliability and Citations ---")

# 1. Answerable question from Exam Notice
req1 = AskRequest(question="What is the exam fee and what happens if I register late?", k=4)
res1 = ask_question(req1)
print("\n[TEST 1] Exam Fee Question:")
print(f"Answer: {res1['answer']}")
print(f"Is Answerable: {res1['is_answerable']}")
print(f"Sources count: {len(res1['sources'])}")
for s in res1['sources']:
    print(f" - {s['source']} (Page {s['page_number']}): {s['snippet'][:80]}...")

# 2. Answerable question from Hostel Notice
req2 = AskRequest(question="Hostel ka curfew time kya hai aur fees kitni hai?", k=4)
res2 = ask_question(req2)
print("\n[TEST 2] Hostel Question (Hindi/Hinglish):")
print(f"Answer: {res2['answer']}")
print(f"Is Answerable: {res2['is_answerable']}")
print(f"Sources count: {len(res2['sources'])}")

# 3. Unanswerable question (Not in any notice)
req3 = AskRequest(question="What is the Sunday dinner menu in the college mess?", k=4)
res3 = ask_question(req3)
print("\n[TEST 3] Unanswerable Question (Mess Sunday Menu):")
print(f"Answer: {res3['answer']}")
print(f"Is Answerable: {res3['is_answerable']}")
print(f"Sources count: {len(res3['sources'])}")

# 4. Out-of-domain question (Completely unrelated)
req4 = AskRequest(question="Who is the president of France and what is the capital?", k=4)
res4 = ask_question(req4)
print("\n[TEST 4] Out-of-domain Question:")
print(f"Answer: {res4['answer']}")
print(f"Is Answerable: {res4['is_answerable']}")
print(f"Sources count: {len(res4['sources'])}")

print("\n--- RAG ANSWER TESTS COMPLETE ---")
