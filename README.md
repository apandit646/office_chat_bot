# Office Policy Chatbot

A chatbot that answers employee questions about company policies (for example, the
*Policy for Reimbursement of Technical Certifications*). It reads your policy PDFs,
stores them in a vector database and uses Google Gemini to answer questions, showing
which document and page each answer came from.

**Stack:** FastAPI · LangGraph · LangChain · ChromaDB · Google Gemini · HTML/CSS/JS frontend

```
Browser (static/)  ──►  FastAPI (app/main.py)  ──►  LangGraph pipeline (app/rag.py)
                                                     rewrite → retrieve → generate
                                                                │          │
                                                           ChromaDB     Gemini
                                                        (chroma_db/)
```

## Project structure

```
office_chatbot/
├── app/
│   ├── config.py    # settings loaded from .env
│   ├── ingest.py    # PDF → chunks → embeddings → ChromaDB
│   ├── rag.py       # LangGraph chatbot (rewrite, retrieve, generate)
│   └── main.py      # FastAPI server + API endpoints
├── static/          # chat web page (index.html, style.css, app.js)
├── data/            # put your policy PDFs here
├── requirements.txt
├── .env.example
└── README.md
```

## Setup

You need **Python 3.10+** and a **Google Gemini API key** (free at
<https://aistudio.google.com/app/apikey>).

### 1. Create a virtual environment and install packages

Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Add your API key

Copy `.env.example` to `.env` and paste your key:

```
GOOGLE_API_KEY=your-real-key
```

### 3. Add your policy PDFs

Copy one or more PDFs into the `data/` folder, for example:

```
data/Policy for Reimbursement of Technical Certifications_Ver_1.01.pdf
```

### 4. Index the documents

```bash
python -m app.ingest
```

This reads every PDF in `data/`, splits it into chunks and saves the embeddings to
`chroma_db/`. **Run it again whenever you add, remove or change a PDF.** Each run
rebuilds the index from scratch.

### 5. Start the server

```bash
uvicorn app.main:app --reload
```

Open **<http://localhost:8000>** and start asking questions.

To let others on your office network use it, run
`uvicorn app.main:app --host 0.0.0.0 --port 8000` and share
`http://<your-computer-ip>:8000`.

## Using the chatbot

- Type a question and press **Enter** (**Shift+Enter** adds a new line), or click one of the suggested questions.
- Follow-up questions work: ask *"What is the certification policy?"* and then *"What about the maximum amount?"*
- Open **Sources** under an answer to see which document and page it came from.
- **+ New chat** starts a fresh conversation.

## API

Interactive API docs (Swagger) are at **<http://localhost:8000/docs>**.

| Method | Endpoint      | Description                                    |
|--------|---------------|------------------------------------------------|
| GET    | `/`           | Chat web page                                  |
| GET    | `/api/health` | Server status and number of indexed chunks     |
| POST   | `/api/chat`   | Ask a question                                 |

**POST `/api/chat`**

Request:

```json
{ "question": "Who is eligible for reimbursement?", "session_id": null }
```

Response:

```json
{
  "answer": "Employees who ...",
  "session_id": "3f2c...",
  "sources": [
    { "source": "Policy for Reimbursement....pdf", "page": 2, "snippet": "..." }
  ]
}
```

Send the returned `session_id` with the next question to continue the same conversation.

Example with curl:

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d "{\"question\": \"What is the maximum reimbursement amount?\"}"
```

## How it works

1. **Ingest** (`app/ingest.py`): `pypdf` extracts the text of each PDF page, `RecursiveCharacterTextSplitter`
   splits it into 1000-character chunks with a 200-character overlap, and `gemini-embedding-001`
   embeddings are stored in ChromaDB.
2. **Rewrite**: if the conversation already has messages, a follow-up like *"What about the
   maximum amount?"* is rewritten into a standalone question so the search finds the right chunks.
3. **Retrieve**: the top 4 most similar chunks are fetched from ChromaDB.
4. **Generate**: `gemini-2.5-flash` answers using only those chunks plus recent chat history.
   If the answer is not in the documents, it says so.

LangGraph's `MemorySaver` stores each conversation in memory by `session_id`.

## Configuration

All settings are optional and go in `.env`:

| Variable          | Default                       | Meaning                          |
|-------------------|-------------------------------|----------------------------------|
| `GOOGLE_API_KEY`  | none (required)               | Gemini API key                   |
| `CHAT_MODEL`      | `gemini-2.5-flash`            | Model that writes the answers    |
| `EMBEDDING_MODEL` | `models/gemini-embedding-001` | Embedding model                  |
| `TOP_K`           | `4`                           | Chunks retrieved per question    |
| `CHUNK_SIZE`      | `1000`                        | Characters per chunk             |
| `CHUNK_OVERLAP`   | `200`                         | Overlap between chunks           |
| `DATA_DIR`        | `data/`                       | Folder containing the PDFs       |
| `CHROMA_DIR`      | `chroma_db/`                  | Where the vector index is stored |

If you change `EMBEDDING_MODEL`, `CHUNK_SIZE` or `CHUNK_OVERLAP`, run `python -m app.ingest` again.

## Troubleshooting

| Problem | Fix |
|---|---|
| `GOOGLE_API_KEY is not set` | Create `.env` from `.env.example` and add your key. |
| Page says *"No documents indexed"* | Put PDFs in `data/` and run `python -m app.ingest`. |
| `No PDF files found` | Check that the files are directly inside `data/` and end in `.pdf`. |
| Activate.ps1 *"running scripts is disabled"* | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once. |
| Page says *"Can't reach the backend"* | Start the server with `uvicorn app.main:app --reload`, then open http://127.0.0.1:8000 (the page also works if you open `static/index.html` directly, as long as the server is running). |
| Answers ignore a PDF you just added | Run `python -m app.ingest` again, then restart the server. |

## Limitations

- Chat history is kept in RAM, so it is lost when the server restarts. For production,
  replace `MemorySaver` with a persistent checkpointer such as `SqliteSaver`.
- There is no login. Put the server behind your company's authentication before
  exposing it outside the office network.
- Scanned (image-only) PDFs contain no text to extract and need OCR first.
