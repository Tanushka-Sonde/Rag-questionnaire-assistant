# Rag-questionnaire-assistant

## Context

Teams regularly receive structured questionnaires such as security reviews, vendor assessments, compliance forms, or operational audits. These questionnaires must be completed using internal documentation and approved information.

Your task is to build a tool that automates this workflow in a structured and reliable way.

### Industry: SaaS (Subscription-based video streaming platform)

The system is designed around a fictional SaaS streaming service similar to platforms like Netflix and Disney+. These companies deliver digital entertainment through cloud infrastructure and subscription-based access.

For this project, the SaaS industry was chosen because its services rely heavily on structured internal documentation such as data security policies, infrastructure descriptions, content delivery architecture, and user authentication mechanisms. This makes it well suited for building a system that retrieves information from reference documents to answer structured questionnaires.

### Company Name: StreamHive

Description:
StreamHive is a SaaS-based video streaming platform that delivers movies, TV shows, and original content to users through a subscription model. The platform provides personalized recommendations, secure content delivery, and multi-device streaming for global audiences. StreamHive serves millions of viewers and uses cloud infrastructure, content delivery networks, and strong data protection practices to ensure reliable and secure media distribution.


## What I Built
An end-to-end AI-powered tool that automates the process of answering structured questionnaires using internal reference documents. Built for **StreamHive** — a fictional B2B SaaS video streaming platform.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit |
| Backend | FastAPI |
| Database | SQLite (via SQLAlchemy) |
| AI | Google Gemini 2.5 Flash Lite via OpenRouter API |
| Retrieval | Custom TF-IDF (no external vector DB needed) |
| Auth | JWT (python-jose) + bcrypt |
| Export | python-docx |

---

## How to Use the Application

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Start the backend (Terminal 1)
```bash
cd "C:\Data\vs codes\Rag-questionnaire-assistant"
uvicorn main:app --reload --port 8000
```

### 3. Start the frontend (Terminal 2)
```bash
streamlit run app.py
```

### 4. Open browser
Navigate to **http://localhost:8501**

---

### Step-by-Step User Flow

**Step 1 — Sign Up & Log In**
- Go to the app, click **Sign Up**, fill in email, username, password
- Then switch to **Log In** tab and log in

**Step 2 — Index Reference Documents**
- Click **Reference Docs** in the sidebar
- Click **Load Default Docs** to index the 6 bundled StreamHive documents
- Or upload your own `.txt` / `.pdf` files

**Step 3 — Create a Run**
- Click **New Run** in the sidebar
- Give your run a name
- Upload `questionnaire.csv` (or any `.csv` / `.txt` questionnaire)
- Click **Create Run & Generate Answers**
- Wait ~10–20 seconds for AI to process all questions

**Step 4 — Review Answers**
- All 14 answers appear on screen with citations and evidence snippets
- A coverage summary shows: Total / Answered / Not Found
- Click **Edit Answer** on any card to modify an answer before export

**Step 5 — Export**
- Click **Download Answers as .docx**
- The exported file preserves original question order with answers and citations below each question

**Step 6 — View Past Runs**
- Click **My Runs** to see all previous runs
- Re-view, re-edit, or re-export any past run

---

## Assumptions Made

1. **TF-IDF over embeddings** — used a custom TF-IDF scorer instead of a vector database to avoid requiring external embedding APIs. This keeps the project fully self-contained.
2. **SQLite for storage** — chosen for zero-config local setup. Swapping to PostgreSQL only requires changing one line in `database.py`.
3. **Single API call for all questions** — all 14 questions are sent in one batch request to avoid rate limits on free-tier APIs.
4. **Global in-memory RAG index** — the retriever is shared in memory and reloaded on each server restart. Production would use a persistent vector store.
5. **OpenRouter as the API gateway** — used OpenRouter to access Gemini 2.5 Flash Lite because the native Gemini API free tier has regional restrictions in India.
6. **Mock reference documents** — the 6 reference `.txt` files are self-created fictional documents representing StreamHive's internal documentation.

---

## Trade-offs

| Decision | Trade-off |
|---|---|
| TF-IDF retrieval | Fast and free — but misses semantic similarity (e.g. "encryption" may not match "cipher") |
| SQLite | Zero setup — not suitable for concurrent production traffic |
| Single batch API call | Saves quota — but if the model returns malformed JSON, all answers fail together |
| Streamlit frontend | Fastest to build — limited real-time UX, no persistent sessions without reload |
| In-memory index | Simple — lost on server restart, must re-load docs each session |
| OpenRouter free tier | No cost — has rate limits; not suitable for high-volume production use |

---

## What I Would Improve With More Time

1. **Semantic vector search** — replace TF-IDF with ChromaDB or Pinecone for embedding-based retrieval, which would significantly improve answer quality for ambiguous or paraphrased questions

2. **Persistent vector store** — so reference documents don't need to be re-indexed on every server restart

3. **Per-user document namespaces** — each user or organization should have isolated reference document collections

4. **Confidence scoring** — use retrieval similarity scores as a proxy for answer confidence, displayed as a badge on each answer card

5. **Partial regeneration** — allow regenerating a single question's answer without re-running the full questionnaire

6. **Version history** — save multiple runs and allow side-by-side comparison of answers across versions

7. **Async generation with progress bar** — use FastAPI background tasks and WebSocket for real-time per-question progress instead of a single blocking call

8. **Better input format support** — handle Excel (`.xlsx`) and Word (`.docx`) questionnaire uploads natively

9. **Docker + cloud deployment** — containerize with Docker Compose and deploy to Railway or Render for a shareable live link

10. **Better PDF parsing** — current pdfplumber approach struggles with scanned PDFs and multi-column layouts; adding OCR support would help