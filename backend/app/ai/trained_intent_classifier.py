"""Lazy, fail-safe access to the trained email intent classifier.

The serialized artifact is produced by ``scripts/train_intent_classifier.py``.
Loading is deliberately optional: an absent/incompatible artifact must never
stop email ingestion, because the deterministic rule classifier remains the
offline-safe fallback.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from app.contracts.schemas import EmailMessage, HackathonCategory

log = logging.getLogger(__name__)
BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_PATH = BACKEND_DIR / "models" / "intent_classifier.joblib"


@dataclass(frozen=True)
class TrainedIntentPrediction:
    category: HackathonCategory
    confidence: float
    model_version: str


_artifact: Optional[dict[str, Any]] = None
_loaded_path: Optional[Path] = None
_load_attempted = False


def model_input(subject: str, body: str, has_attachments: bool) -> str:
    """Build the exact text representation shared by training and inference."""
    attachment_marker = "HAS_ATTACHMENTS" if has_attachments else "NO_ATTACHMENTS"
    return f"SUBJECT {subject or ''}\n{attachment_marker}\nBODY {body or ''}"


def configured_model_path() -> Path:
    raw = os.environ.get("INTENT_MODEL_PATH", "").strip()
    if not raw:
        return DEFAULT_MODEL_PATH
    path = Path(raw)
    return path if path.is_absolute() else BACKEND_DIR / path


def _load_artifact() -> Optional[dict[str, Any]]:
    global _artifact, _loaded_path, _load_attempted
    if os.environ.get("INTENT_MODEL_ENABLED", "1").strip().lower() in {"0", "false", "no"}:
        return None
    path = configured_model_path()
    if _load_attempted and _loaded_path == path:
        return _artifact
    _load_attempted, _loaded_path, _artifact = True, path, None
    if not path.is_file():
        log.info("Intent model not found at %s; using deterministic rules", path)
        return None
    try:
        import joblib

        loaded = joblib.load(path)
        if not isinstance(loaded, dict) or "pipeline" not in loaded:
            raise ValueError("artifact must be a dictionary containing 'pipeline'")
        _artifact = loaded
    except Exception as exc:
        log.warning("Could not load intent model %s (%s); using rules", path, type(exc).__name__)
    return _artifact


def predict_trained_intent(email: EmailMessage, has_attachments: bool) -> Optional[TrainedIntentPrediction]:
    artifact = _load_artifact()
    if not artifact:
        return None
    pipeline = artifact["pipeline"]
    text = model_input(email.subject or "", email.body or "", has_attachments)
    try:
        probabilities = pipeline.predict_proba([text])[0]
        classes = pipeline.classes_
        index = int(probabilities.argmax())
        category = HackathonCategory(str(classes[index]))
        return TrainedIntentPrediction(
            category=category,
            confidence=round(float(probabilities[index]), 4),
            model_version=str(artifact.get("model_version", "unknown")),
        )
    except Exception as exc:
        log.warning("Intent model prediction failed (%s); using rules", type(exc).__name__)
        return None


def reset_model_cache() -> None:
    """Clear the lazy loader; useful after training and in isolated tests."""
    global _artifact, _loaded_path, _load_attempted
    _artifact, _loaded_path, _load_attempted = None, None, False
