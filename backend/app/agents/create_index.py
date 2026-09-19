#!/usr/bin/env python3
"""
Build / refresh the vector index used by Ask-AI (mirrors `create_index.py` in the
langgraph-email-automation reference).

    cd backend
    python -m app.agents.create_index                 # knowledge folder + every case in the repository
    python -m app.agents.create_index --knowledge-only
    python -m app.agents.create_index --data-dir ./data --limit 100

Env: EMBEDDING_PROVIDER=gemini|openai|local, VECTOR_STORE=supabase|local (see agents/rag.py).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

from app.agents.rag import DATA_DIR, case_chunks, get_rag, knowledge_chunks  # noqa: E402
from app.config import get_repo  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=str(DATA_DIR))
    ap.add_argument("--knowledge-only", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    rag = get_rag()
    n = rag.index(knowledge_chunks(Path(args.data_dir)))
    print(f"knowledge chunks indexed: {n}")
    if not args.knowledge_only:
        repo = get_repo()
        cases = repo.list_cases()
        if args.limit:
            cases = cases[: args.limit]
        total = 0
        batch = []
        for c in cases:
            e = repo.get_email(c.source_email_id)
            if not e:
                continue
            batch.extend(case_chunks(c, e))
            if len(batch) >= 300:
                total += rag.index(batch)
                batch = []
        total += rag.index(batch)
        print(f"case chunks indexed: {total} (from {len(cases)} cases)")
    print("index info:", rag.info())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
