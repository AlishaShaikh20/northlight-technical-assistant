# Northlight Technical Online Assistant

A Retrieval-Augmented Generation (RAG) chatbot that answers questions from company policy PDFs and shows exactly where each answer came from. When two documents give different instructions, it reports the conflict instead of silently picking one.

**Live demo:** _add your link here_ &nbsp;|&nbsp; **Screenshot:** _add a screenshot here_

## Highlights

- **Grounded answers.** The LLM only sees retrieved document chunks and cites the source file for every fact.
- **Conflict detection.** If sources disagree, the answer starts with "The documents disagree:" and lists what each file says. The UI shows it in an amber warning card.
- **Honest refusals.** If the answer isn't in the documents, it says so instead of guessing.
- **Ambiguity handling.** If a number is unclear (for example, per person or in total), it states the ambiguity instead of calculating a total the documents never gave.
- **Verify in one click.** Source chips and a document browser open the original text, with the cited passage highlighted.
- **Guided demo.** A new chat offers four starter questions, each labeled with the behavior it demonstrates, so a reviewer can test the system without reading the PDFs.

## How It Works

```text
PDFs → section-based chunking → MiniLM embeddings → ChromaDB
                                                       ↓
Question → embedding → top-5 semantic search → Groq LLM → answer + sources
```

1. **Load.** PyMuPDF extracts text from every PDF in `PDFS/`.
2. **Chunk.** Text is split at section headings (`3. Home Office Stipend`), FAQ questions (`Q: ...`) and named sections. Anything over 800 characters falls back to a recursive splitter (800 characters, 150 overlap). The five PDFs become 34 chunks.
3. **Embed.** Each chunk is encoded with `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions, normalized).
4. **Store.** Vectors go into ChromaDB using cosine distance, with deterministic chunk IDs and `upsert` so re-running ingestion never creates duplicates.
5. **Retrieve.** The question is embedded and the 5 closest chunks are returned with similarity scores.
6. **Generate.** A Groq-hosted LLM answers using a strict system prompt: answer only from context, cite files, flag conflicts, refuse when unknown, and never assume ambiguous totals.
7. **Display.** The answer, source chips, retrieved chunks with scores, and a document viewer are shown in the web UI.

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python |
| LLM | Groq (`openai/gpt-oss-120b`) |
| Embeddings | Sentence Transformers, `all-MiniLM-L6-v2` |
| Vector database | ChromaDB |
| PDF processing | PyMuPDF |
| Text splitting | LangChain text splitters |
| Backend | Flask |
| Frontend | HTML, CSS, JavaScript |
| Demo hosting | Modal / ngrok |

## Evaluation

The pipeline was tested on seven questions chosen to expose typical RAG failures.

| Question | What it tests | Result |
|---|---|---|
| Where do I request access to a new tool? | Conflicting sources (`#it-requests` vs `#access-requests`) | Pass: conflict reported, all three files cited |
| What happens to my laptop and account when I leave? | Single-section lookup | Pass |
| How much is the home office stipend and when can I claim it? | Multiple numbers in one section | Pass: $750 after 30 days and $300 annual refresh |
| What is the salary band for a senior engineer? | Answer not in the documents | Pass: refuses, no invented numbers |
| If I relocate abroad, what do I need to do? | Policy that touches benefits | Pass: notice period and legal review, nothing invented |
| I'm on the PPO with a spouse and two kids, what's my cost? | Ambiguous pricing | Pass after a prompt fix: shows both readings |
| Can I use my personal laptop for customer data? | Policy lookup | Pass |

### Problems found and fixed

- **Duplicate chunks.** Re-running the ingestion cell added every chunk again under new random IDs. Fixed with deterministic IDs and `upsert`.
- **Wrong similarity score.** `1 - distance` is not cosine similarity for Chroma's default metric, and it silently filtered out valid results. Fixed by using cosine distance.
- **Chunks cutting through sections.** Fixed-size splitting separated the $750 stipend from the $300 refresh and buried the `#access-requests` answer in a large chunk. Section-based splitting fixed both.
- **Confident guesses on unclear data.** The model multiplied an ambiguous dependent cost. An explicit ambiguity rule in the system prompt fixed it.

## Project Structure

```text
northlight-technical-assistant/
├── PDFS/                        # source documents
├── static/
│   ├── app.js
│   └── style.css
├── templates/
│   └── index.html
├── data/vector_store/           # ChromaDB storage
├── app.py                       # Flask app and API routes
├── rag_chatbot_pipeline.py      # chunking, embeddings, retrieval, generation
├── rag_chatbot_pipeline.ipynb   # development notebook
├── requirements.txt
└── README.md
```

## Run Locally

```bash
git clone https://github.com/AlishaShaikh20/northlight-technical-assistant.git
cd northlight-technical-assistant

python -m venv venv
.\venv\Scripts\Activate.ps1          # Windows (macOS/Linux: source venv/bin/activate)

pip install -r requirements.txt
$env:GROQ_API_KEY="your_api_key_here"   # macOS/Linux: export GROQ_API_KEY=...

python app.py
```

Open `http://127.0.0.1:5000`. The first start downloads the embedding model, so it takes a little longer. Never commit your API key.

## API

| Endpoint | Description |
|---|---|
| `GET /` | Chat interface |
| `POST /ask` | Takes `{"question": "..."}` and returns the answer, a type, and sources |
| `GET /docs` | Returns each PDF's title and extracted text for the document viewer |

Example `/ask` response:

```json
{
  "answer": "The documents disagree: ...",
  "type": "warn",
  "sources": [
    { "file": "05_Remote_Tools_and_Communication_Guide.pdf", "text": "...", "score": 0.78 }
  ]
}
```

`type` is `ok`, `warn` (sources conflict) or `none` (not in the documents).

## Deployment Notes

For demos, expose the local app with ngrok and keep both the Flask app and the tunnel running. A permanent deployment needs a host with enough memory for the embedding model. Set `GROQ_API_KEY` as a secret on the host instead of putting it in code.

## Limitations and Future Work

- The document viewer shows extracted text, not the original PDF layout.
- Chunking rules are tuned to these five documents and would need adjusting for other formats.
- Planned: PDF upload, hybrid keyword + semantic search, streaming responses, conversation history, and automated retrieval evaluation.

## Author

**Alisha Shaikh**: AI/ML Engineer | Python | Machine Learning | Generative AI

GitHub: [AlishaShaikh20](https://github.com/AlishaShaikh20)

