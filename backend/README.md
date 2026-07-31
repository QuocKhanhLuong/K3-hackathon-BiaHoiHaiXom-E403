# VLearn Backend

FastAPI application layer for the VLearn Learning Loop. The backend owns HTTP
contracts, anonymous session isolation, conversation/turn/action state, slide
context retrieval, and the adapter to `ai_core`.

## Local setup

Run from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements-dev.txt
python -m pip install -e ai_core
Copy-Item .env.example .env
python -m uvicorn backend.main:app --port 8000
```

### Optional local semantic retrieval

Semantic retrieval is disabled by default (`AI_RAG_SEMANTIC_ENABLED=false`) so
the normal deployment is BM25/lexical-only and does not load or provision an
embedding model. To opt in on a sufficiently sized machine, install
`ai_core[rag-semantic]`, pre-provision
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` with
`python -m backend.app.retrieval.provision_embeddings`, then set
`AI_RAG_SEMANTIC_ENABLED=true`. The request path uses `local_files_only=True`:
it never downloads a model. If the optional provider is unavailable, VLearn
records `semantic_fallback_reason` and uses lexical retrieval. Generated
embedding indexes live under `backend/.generated/vlearn_rag/`, which is
Git-ignored.

Open `http://localhost:8000`.

The OpenAI key is configured only in the server environment. API requests do
not accept provider keys.

## Test

```powershell
python -m pytest -q backend/tests
python -m pytest -q ai_core/tests -m "not live"
```

## Structure

```text
backend/app/
  api/             Versioned and frontend-compatibility routes
  application/     Turn/conversation state transitions
  ai/              Adapter and public-result mapper
  persistence/     Phase 1 memory repository
  retrieval/       Local slide repository
  schemas/         Strict public API DTOs
```

`backend.main:app` remains the stable Uvicorn entrypoint.

## Phase 1 limitation

The repository and LangGraph checkpointer are still process-local memory.
Restart and multi-worker persistence are deliberately scheduled for Phase 2.
