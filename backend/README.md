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
