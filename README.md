# RAG PDF Q&A (Flask + Groq)

Upload a PDF, ask questions about it, get answers grounded in the document
using retrieval-augmented generation.

## How it works

1. **Upload** — PDF text is extracted (`PyPDF2`), split into overlapping chunks.
2. **Embed** — each chunk is embedded with `sentence-transformers` (`all-MiniLM-L6-v2`, runs locally, no API needed).
3. **Index** — chunk embeddings are stored in an in-memory **FAISS** index (cosine similarity).
4. **Ask** — your question is embedded the same way, the top-matching chunks are retrieved, and sent as context to **Groq** (Llama 3.1) to generate the final answer.

## Setup

```bash
cd rag_app
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Add your Groq API key

This project uses a `.env` file (loaded automatically via `python-dotenv`).

1. A `.env` file is already included — just open it and replace the placeholder:

   ```
   GROQ_API_KEY=your_groq_api_key_here
   ```

   with your real key from https://console.groq.com (free, no credit card needed).

2. If you ever regenerate the project from scratch, copy `.env.example` to `.env` first:

   ```bash
   cp .env.example .env
   ```

**Important:** never commit your real `.env` to GitHub — it's already listed in `.gitignore`.

Optional variables you can also set in `.env`:

```
GROQ_MODEL=llama-3.1-8b-instant
PORT=8000
FLASK_SECRET_KEY=change-this-to-something-random
```

## Run

```bash
python app.py
```

Open **http://localhost:8000** in your browser.

- First run will download the `all-MiniLM-L6-v2` embedding model (~90MB) — needs internet access once, then it's cached locally.
- Upload a PDF, wait for "processed successfully", then ask questions in the chat box.

## Notes for your assignment write-up

- **Chunking**: 800 characters per chunk, 150-character overlap (configurable at top of `app.py`).
- **Retrieval**: top-4 most similar chunks per question (`TOP_K` in `app.py`), using FAISS `IndexFlatIP` on normalized embeddings (= cosine similarity).
- **Generation**: retrieved chunks + question are sent to Groq's Llama model with a system prompt instructing it to answer only from the given context.
- **Session handling**: each browser session gets its own uploaded document and FAISS index (stored in memory, keyed by Flask session ID) — good enough for a demo/assignment; for production you'd persist this in a real vector DB.
- Uploaded PDF files are deleted from disk right after text extraction — only the extracted text/embeddings are kept in memory.

## File structure

```
rag_app/
├── app.py              # Flask backend: upload, chunk, embed, retrieve, ask Groq
├── requirements.txt
├── templates/
│   └── index.html      # Upload + chat UI
├── static/
│   ├── style.css
│   └── script.js
└── uploads/             # temp storage for uploaded PDFs (auto-cleared)
```

python -m venv venv
 venv\Scripts\activate 
pip install recns.txt
python app.py
