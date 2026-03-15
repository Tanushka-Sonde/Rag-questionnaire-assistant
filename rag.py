import os, re, json, time, requests
from typing import List, Dict

OPENROUTER_API_KEY = "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"
MODEL_NAME = "google/gemini-2.5-flash-lite"
SITE_URL = "http://localhost:8000"
SITE_NAME = "RAG Questionnaire Assistant"

HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": SITE_URL,
    "X-Title": SITE_NAME
}

def call_openrouter(prompt: str) -> str:
    url = "https://openrouter.ai/api/v1/chat/completions"
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0
    }
    for attempt in range(3):
        response = requests.post(url, headers=HEADERS, data=json.dumps(payload))
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"].strip()
        elif response.status_code == 429:
            print(f"Rate limit hit, waiting 10s...")
            time.sleep(10)
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return ""
    return ""


# ─── Simple TF-IDF retriever ─────────────────────────────────────────────────

class TFIDFRetriever:
    def __init__(self):
        self.chunks: List[Dict] = []

    def add_document(self, text: str, source: str, chunk_size: int = 300):
        words = text.split()
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i : i + chunk_size])
            self.chunks.append({"text": chunk, "source": source})

    def _score(self, query: str, chunk: str) -> float:
        q_terms = set(re.findall(r"\w+", query.lower()))
        c_terms = re.findall(r"\w+", chunk.lower())
        if not c_terms:
            return 0.0
        hits = sum(1 for t in c_terms if t in q_terms)
        return hits / len(c_terms)

    def retrieve(self, query: str, top_k: int = 3) -> List[Dict]:
        scored = [(self._score(query, c["text"]), c) for c in self.chunks]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for score, c in scored[:top_k] if score > 0]

    def get_all_text(self) -> str:
        parts = [f"[{c['source']}]\n{c['text']}" for c in self.chunks]
        return "\n\n".join(parts)


# ─── RAG Engine ──────────────────────────────────────────────────────────────

class RAGEngine:
    def __init__(self):
        self.retriever = TFIDFRetriever()
        self._docs: List[str] = []

    def list_docs(self) -> List[str]:
        return self._docs

    def index_document(self, path: str, display_name: str):
        ext = os.path.splitext(path)[1].lower()
        text = ""
        if ext in [".txt", ".md"]:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        elif ext == ".pdf":
            try:
                import pdfplumber
                with pdfplumber.open(path) as pdf:
                    text = "\n".join(p.extract_text() or "" for p in pdf.pages)
            except Exception as e:
                text = f"[PDF parse error: {e}]"
        if text.strip():
            self.retriever.add_document(text, display_name)
            if display_name not in self._docs:
                self._docs.append(display_name)

    def answer_all_questions(self, questions: List[Dict]) -> List[Dict]:
        """Answer ALL questions in a single API call."""
        all_context = self.retriever.get_all_text()

        if not self.retriever.chunks:
            return [{"answer": "Not found in references.", "citations": []} for _ in questions]

        q_block = "\n".join(f"Q{q['id']}: {q['text']}" for q in questions)

        prompt = f"""You are a precise technical documentation assistant.
Answer each question ONLY using the reference documents provided.
If a question cannot be answered from the documents, write exactly: "Not found in references."
Respond in valid JSON only — a JSON array, nothing else, no markdown fences.

--- REFERENCE DOCUMENTS ---
{all_context}

--- QUESTIONS ---
{q_block}

Return a JSON array like this:
[
  {{"id": "Q1", "answer": "Your answer here", "citations": ["source1.txt"]}},
  ...
]"""

        raw = call_openrouter(prompt)
        if not raw:
            return [{"answer": "Not found in references.", "citations": []} for _ in questions]

        try:
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
            parsed = json.loads(raw)
        except Exception as e:
            print(f"JSON parse error: {e}\nRaw: {raw[:500]}")
            return [{"answer": "Not found in references.", "citations": []} for _ in questions]

        results = []
        id_map = {str(item["id"]).replace("Q", "").strip(): item for item in parsed}
        for q in questions:
            qid = str(q["id"]).replace("Q", "").strip()
            item = id_map.get(qid) or id_map.get(f"Q{qid}") or {}
            answer = item.get("answer", "Not found in references.")
            cited_sources = item.get("citations", [])

            citations = []
            for src in cited_sources:
                for chunk in self.retriever.chunks:
                    if chunk["source"].lower() in src.lower() or src.lower() in chunk["source"].lower():
                        citations.append({
                            "source": chunk["source"],
                            "snippet": chunk["text"][:200].replace("\n", " ")
                        })
                        break

            if not citations and answer != "Not found in references.":
                top = self.retriever.retrieve(q["text"], top_k=2)
                for c in top:
                    citations.append({"source": c["source"], "snippet": c["text"][:200].replace("\n", " ")})

            results.append({"answer": answer, "citations": citations})
        return results

    def answer_question(self, question: str) -> Dict:
        """Single question fallback."""
        chunks = self.retriever.retrieve(question, top_k=4)
        if not chunks:
            return {"answer": "Not found in references.", "citations": []}
        context_block = "\n\n".join(f"[{c['source']}]\n{c['text']}" for c in chunks)
        prompt = f"Answer only from references. If not found say 'Not found in references.'\n\n{context_block}\n\nQuestion: {question}"
        answer = call_openrouter(prompt) or "Not found in references."
        citations = [{"source": c["source"], "snippet": c["text"][:200].replace("\n", " ")} for c in chunks]
        return {"answer": answer, "citations": citations}