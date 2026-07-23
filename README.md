# 🔬 AI Research Assistant

## 🚀 Project Overview

**AI Research Assistant** is a full-stack, agentic RAG (Retrieval-Augmented Generation) system that helps researchers find, understand, and synthesize information across academic papers — without manually downloading and reading each one.

Ask a question in plain language and get a grounded answer pulled directly from relevant papers, including exact numeric results, table data, and even figures/diagrams — or let the system autonomously search arXiv and CORE for new papers when your existing library doesn't have enough coverage.

The assistant enables researchers to:

* Ask natural-language questions about any paper, or across their entire library
* Auto-fetch relevant papers by topic from arXiv and CORE — no manual downloading
* Compare results and methodologies across multiple papers
* Extract exact numeric results from tables (RMSE, MAE, R², accuracy, etc.)
* Understand figures, charts, and diagrams via vision-model captioning
* Organize papers into topic-based **Research Sessions**
* Generate structured, exportable **PDF literature review reports**
* Let an autonomous agent decide when the library needs new papers and fetch them mid-conversation

---

## 🧠 Architecture

The system follows a full extraction → retrieval → generation pipeline, wrapped in an agentic decision layer:

<img width="1745" height="1241" alt="architecture" src="https://github.com/user-attachments/assets/2b112963-a6e0-4d93-9322-e3d1cb300b96" />


## ✨ Core Features

### 1️⃣ Grounded Question Answering
Ask anything about a specific paper, a comparison across papers, or your library in general. Every answer cites its sources, rendered as footnote-style citations.

### 2️⃣ Autonomous Research Agent
For open-ended topic questions, the agent:
- Retrieves from the existing library and judges whether coverage is genuinely sufficient
- If not, autonomously searches arXiv, downloads, and ingests new papers
- Re-checks coverage after fetching, and is explicit in its reasoning log if the fetch didn't fully close the gap — no hallucinated confidence

### 3️⃣ Multi-Source Paper Discovery
- **arXiv API** — free, no key required
- **CORE API** — broader coverage of published/peer-reviewed papers, with automatic fallback to alternate source URLs and caching of known-dead links

### 4️⃣ Hybrid Retrieval + Reranking
- **Vector search** (semantic similarity) + **BM25** (exact keyword matching) blended together
- A **cross-encoder reranker** re-scores the shortlist for final precision, catching cases where embedding similarity alone would mislead

### 5️⃣ Table & Figure Understanding
- Dedicated table extraction (`pdfplumber`) for numeric results, not just prose summaries
- Vision-LLM figure captioning — circuit diagrams, architecture diagrams, charts, and confusion matrices become genuinely searchable content

### 6️⃣ Research Sessions
Papers are organized into topic-based sessions (auto-created on topic-fetch, or chosen manually on upload) — browsable as a tabbed card catalog with star/delete, each paper tagged by origin (arXiv / CORE / manual upload).

### 7️⃣ Report Generation
One click compiles a session's papers into a structured literature review — Introduction, Comparative Analysis, Research Gaps, Conclusion — exported as a clean, styled PDF.

### 8️⃣ Conversation Memory & Multi-Chat
Follow-up questions resolve correctly without repeating paper names. Multiple persistent, named conversations, like a real chat app.

---

## 🛠️ Tech Stack

Chosen to be **fully free** to run, while remaining production-representative:

| Component | Choice | Why |
|---|---|---|
| Backend | **FastAPI** | Async-friendly, automatic interactive docs (`/docs`) |
| Frontend | Custom HTML / CSS / JS | Distinct, purpose-built interface — not a generic chatbot template |
| LLM (generation) | Groq — `openai/gpt-oss-120b` | Free tier, extremely fast inference |
| LLM (routing / agent reasoning) | Groq — `openai/gpt-oss-20b` | Smaller/faster/cheaper for high-frequency classification calls |
| Vision (figure captioning) | Groq — `qwen/qwen3.6-27b` | Free, multimodal, describes charts/diagrams |
| Embeddings | HuggingFace `sentence-transformers/all-MiniLM-L6-v2` | Local, free, no API cost |
| Reranking | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Local, free, precision boost on top of hybrid search |
| Vector DB | ChromaDB | Free, local, persistent |
| Keyword search | `rank-bm25` | Complements vector search for exact-term matching |
| Orchestration | LangChain | RAG scaffolding without hiding the fundamentals |
| PDF text | PyMuPDF (`fitz`) | Reliable extraction, handles multi-column academic layouts |
| PDF tables | `pdfplumber` | Structured table extraction for numeric results |
| Report export | `markdown` + `xhtml2pdf` | Pure-Python PDF generation, no native binary dependencies |
| Paper discovery | arXiv API, CORE API | Free, low-friction |

---

## 📁 Project Structure

```
src/
├── extraction/     # PDF text, table, and image extraction
├── chunking/       # Section-aware chunking with normalized labels
├── embeddings/     # Local embedding model wrapper
├── vectordb/       # ChromaDB build/query/delete logic
├── retrieval/      # Vector search, BM25, hybrid search, reranking, paper-scoped retrieval
├── llm/            # Groq client, LLM-based router, prompt templates
├── ingestion/      # Single-PDF pipeline (used by upload + discovery)
├── discovery/      # arXiv and CORE search + auto-ingestion, dead-link caching
├── library/        # Paper registry + research session (topic) management
├── chat/           # Multi-chat persistence
├── core/           # Shared chat-answering logic (used by the API layer)
├── reports/        # Per-session report generation (summarize → synthesize → PDF)
└── agent/          # Autonomous research agent (coverage check + auto-fetch)

app.py                  # FastAPI application (routes for chat, sessions, papers, reports)
templates/index.html     # Frontend shell
static/css/style.css     # "Reading Room" design system
static/js/app.js         # Frontend logic (fetch calls, rendering, interactivity)
```

---

## 🧩 How Retrieval & Routing Work

A single query can be answered in several different ways depending on intent — decided by an **LLM-based router**, not keyword matching (an earlier, more fragile approach replaced after repeated real-world failures):

* **Single paper question** → hybrid search + reranking, scoped to just that paper
* **Comparison question** → pulls results-tagged content from each named paper, with a semantic-search fallback for papers whose results section wasn't cleanly tagged
* **Library/meta question** ("what papers do I have") → answered directly from the paper registry, no LLM call needed
* **Recent papers question** → resolved via a persistent registry tracking add-order
* **General/open-ended question** → routed to the **autonomous research agent**, which checks coverage and fetches new papers if needed before answering

Paper names extracted by the router are **fuzzy-matched** against the real library, since LLMs don't always reproduce long filenames character-perfectly.

---

## 📸 Interface Preview



**🔗 Live Demo:** [https://research-rag-mhbe.onrender.com](https://research-rag-mhbe.onrender.com)

> Hosted on Render's free tier — the service may take 30–60 seconds to wake up on first load if it's been idle. The demo comes pre-loaded with sample papers, so try asking questions directly rather than uploading new PDFs (uploads are slow on free-tier CPU due to embedding + figure captioning).
The frontend uses a custom "Reading Room" design system — dark ink backgrounds, aged-paper message cards, footnote-style citations, and index-card-styled paper entries with origin tabs (arXiv / CORE / manual upload) — built to feel like a scholar's card catalog rather than a generic chat template.

---

## ⚙️ Setup

```bash
# 1. Clone and create a virtual environment
git clone <your-repo-url>
cd ai-research-assistant
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up API keys in a .env file
GROQ_API_KEY=your_groq_key
CORE_API_KEY=your_core_key      # optional, for CORE paper discovery

# 4. Run the app
uvicorn app:app --reload --port 5000
```

Then open:
* **http://127.0.0.1:5000** — the application
* **http://127.0.0.1:5000/docs** — FastAPI's interactive API explorer

---

## 📌 How to Use

1. **Upload a PDF** or **fetch papers by topic** (arXiv / CORE / both) from the sidebar
2. Choose or create a **Research Session** (topic) to organize the paper under
3. Ask questions in the chat — about a specific paper, a comparison, or a broad topic
4. If your library lacks coverage on a broad topic, the **research agent** will automatically search for and add relevant papers before answering
5. Open a session to **generate a report** — a structured PDF literature review of everything in that topic
6. Manage your library: star sessions, delete papers or reports, browse chat history

---

## 🔍 Known Limitations / Honest Gaps

* **CORE API reliability** — some CORE-indexed PDFs return broken links; automatic fallback and dead-link caching mitigate this, but not every paper has a working link anywhere
* **Image captioning is not retroactive** — papers ingested before this feature existed lack figure/diagram chunks; new ingestions get it automatically
* **Comparison queries can occasionally miss a paper** if its results section wasn't detected by heading-based chunking (a semantic-search fallback covers explicitly-named comparisons, but not broad "compare all papers" queries, for performance reasons)
* **Report generation cost scales with session size** — larger sessions take proportionally longer and use more tokens
* **The research agent's fetch quality depends on arXiv's own search relevance** — for very niche or emerging topics, arXiv may not have a strong match, and the agent will honestly report this rather than force an answer

---

## 🎯 What This Project Demonstrates

Built incrementally, with most features validated against **real failures** rather than assumed to work — surfacing genuine engineering lessons:

* Naive character-based chunking loses document structure; section-aware chunking with normalization is meaningfully better
* Cosine similarity (not default L2 distance) matters for sentence-transformer embeddings
* Table data is often unreadable by plain text extraction — dedicated table extraction is necessary for numeric results
* Keyword-based intent classification breaks on real phrasing; a single LLM-based router is more robust and, counter-intuitively, often *faster* since it replaces multiple sequential heuristic calls
* Self-referential confusion (an LLM doubting content because a paper's filename doesn't literally appear in its own text) is a real, recurring failure mode requiring explicit prompt handling
* Aggregator APIs (CORE) have inherent data-quality gaps that need graceful degradation and caching of known failures, not just retries
* Vision models can meaningfully extend RAG beyond text — diagrams and charts become genuinely searchable content, not blind spots
* URL path parameters aren't equally reliable as query parameters for arbitrary strings — a comma in a paper title silently broke a delete endpoint until moved to a query string
* Reranking with a cross-encoder measurably improves final answer precision over hybrid search alone, especially on comparison-heavy queries
* An autonomous agent is only trustworthy if it verifies its own actions worked — a fetch-then-assume-success loop is worse than one that re-checks coverage and reports honestly when a fetch didn't help

---

## 📄 License

This project was built as a learning exercise in RAG system design and agentic AI. Feel free to fork, learn from, or build on it.
