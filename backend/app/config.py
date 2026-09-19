"""Runtime configuration + repository factory."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from app.repositories.base import BaseRepository
from app.repositories.memory import MemoryRepository

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


BUNDLE_DIR = Path(env("BUNDLE_DIR", str(ROOT_DIR / "sdoc-hackathon-bundle")))
SEED_SNAPSHOT = Path(env("SEED_SNAPSHOT", str(ROOT_DIR / "supabase" / "seed" / "snapshot.json")))
REPO_BACKEND = env("REPO_BACKEND", "memory").lower()
AUTO_SEED = env("AUTO_SEED", "1") == "1"
DEMO_USER_ID = env("DEMO_USER_ID", "u_sup_1")


@lru_cache(maxsize=1)
def get_repo() -> BaseRepository:
    if REPO_BACKEND == "supabase":
        from app.repositories.supabase_repo import SupabaseRepository

        return SupabaseRepository()
    repo = MemoryRepository()
    if AUTO_SEED and SEED_SNAPSHOT.exists():
        repo.load_file(SEED_SNAPSHOT)
    return repo
