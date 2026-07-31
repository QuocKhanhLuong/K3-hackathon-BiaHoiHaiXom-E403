"""Keep deterministic evaluation tests independent of local embedding weights."""

import os

os.environ.setdefault("AI_RAG_SEMANTIC_ENABLED", "false")
