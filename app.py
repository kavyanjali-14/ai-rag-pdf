import os
import uuid
import pickle

from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template, session
from werkzeug.utils import secure_filename

from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
load_dotenv()  # reads variables from a .env file in the project root, if present

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {"pdf"}
CHUNK_SIZE = 800        # characters per chunk
CHUNK_OVERLAP = 150     # overlap between chunks
TOP_K = 4               # number of chunks retrieved per question

# Groq API (OpenAI-compatible endpoint)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# ---------------------------------------------------------------------------
# In-memory store: { session_id: {"chunks": [...], "index": faiss_index} }
# For a class assignment this is fine. For production, use a real DB / vector store.
# ---------------------------------------------------------------------------
STORE = {}

# Load the embedding model once at startup (downloads on first run, then cached)
print("Loading embedding model (all-MiniLM-L6-v2)...")
embedder = SentenceTransformer("all-MiniLM-L6-v2")
EMBED_DIM = embedder.get_sentence_embedding_dimension()
print("Embedding model ready. Dim =", EMBED_DIM)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text_from_pdf(filepath):
    reader = PdfReader(filepath)
    text_parts = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        text_parts.append(page_text)
    return "\n".join(text_parts)


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    text = " ".join(text.split())  # normalize whitespace
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return [c for c in chunks if c.strip()]


def build_faiss_index(chunks):
    embeddings = embedder.encode(chunks, convert_to_numpy=True, normalize_embeddings=True)
    index = faiss.IndexFlatIP(EMBED_DIM)  # cosine similarity via normalized inner product
    index.add(embeddings.astype("float32"))
    return index


def retrieve_top_chunks(session_id, question, k=TOP_K):
    entry = STORE.get(session_id)
    if not entry:
        return []
    q_embedding = embedder.encode([question], convert_to_numpy=True, normalize_embeddings=True)
    scores, idxs = entry["index"].search(q_embedding.astype("float32"), k)
    results = []
    for score, idx in zip(scores[0], idxs[0]):
        if idx == -1:
            continue
        results.append(entry["chunks"][idx])
    return results


def ask_groq(question, context_chunks):
    if not GROQ_API_KEY:
        return "Server is missing GROQ_API_KEY. Set it as an environment variable and restart the app."

    context = "\n\n---\n\n".join(context_chunks)
    system_prompt = (
        "You are a helpful assistant that answers questions using ONLY the provided "
        "document context. If the answer is not in the context, say you don't know "
        "based on the document. Be concise and accurate."
    )
    user_prompt = f"Document context:\n{context}\n\nQuestion: {question}\n\nAnswer:"

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 512,
    }
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    resp = requests.post(GROQ_API_URL, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
    session_id = session["session_id"]

    if "pdf_file" not in request.files:
        return jsonify({"error": "No file part in the request."}), 400

    file = request.files["pdf_file"]
    if file.filename == "":
        return jsonify({"error": "No file selected."}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Only PDF files are allowed."}), 400

    filename = secure_filename(f"{session_id}_{file.filename}")
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    try:
        text = extract_text_from_pdf(filepath)
        if not text.strip():
            return jsonify({"error": "Could not extract any text from this PDF (it may be scanned/image-only)."}), 400

        chunks = chunk_text(text)
        index = build_faiss_index(chunks)
        STORE[session_id] = {"chunks": chunks, "index": index, "filename": file.filename}

        return jsonify({
            "message": f"'{file.filename}' processed successfully.",
            "num_chunks": len(chunks),
        })
    except Exception as e:
        return jsonify({"error": f"Failed to process PDF: {str(e)}"}), 500
    finally:
        # Clean up the uploaded file from disk; we only keep the text/embeddings in memory
        if os.path.exists(filepath):
            os.remove(filepath)


@app.route("/ask", methods=["POST"])
def ask():
    if "session_id" not in session or session["session_id"] not in STORE:
        return jsonify({"error": "Please upload a PDF first."}), 400

    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "Question cannot be empty."}), 400

    session_id = session["session_id"]
    top_chunks = retrieve_top_chunks(session_id, question)

    if not top_chunks:
        return jsonify({"answer": "I couldn't find relevant content in the document for that question."})

    try:
        answer = ask_groq(question, top_chunks)
        return jsonify({"answer": answer, "sources": top_chunks})
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Groq API request failed: {str(e)}"}), 502


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=True)
