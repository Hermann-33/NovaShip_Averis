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


def resolve_path(value: str, base: Path) -> Path:
    """Resolve relative env paths against the repo (or backend) root, not the process cwd."""
    path = Path(value)
    if path.is_absolute():
        return path
    rooted = (base / path).resolve()
    cwd_path = (Path.cwd() / path).resolve()
    if rooted.exists() or not cwd_path.exists():
        return rooted
    return cwd_path


BUNDLE_DIR = resolve_path(env("BUNDLE_DIR", str(ROOT_DIR / "sdoc-hackathon-bundle")), ROOT_DIR)
SEED_SNAPSHOT = resolve_path(
    env("SEED_SNAPSHOT", str(ROOT_DIR / "supabase" / "seed" / "snapshot.json")),
    ROOT_DIR,
)
REPO_BACKEND = env("REPO_BACKEND", "memory").lower()
AUTO_SEED = env("AUTO_SEED", "1") == "1"


@lru_cache(maxsize=1)
def get_repo() -> BaseRepository:
    if REPO_BACKEND == "supabase":
        from app.repositories.supabase_repo import SupabaseRepository

        return SupabaseRepository()
    repo = MemoryRepository()
    if AUTO_SEED and SEED_SNAPSHOT.exists():
        repo.load_file(SEED_SNAPSHOT)
    return repo
