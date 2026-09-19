"""
Tools the agents may call. Deterministic business logic is exposed as tools so
an LLM can *invoke* it but never *replace* it.
"""
from __future__ import annotations

from typing import Any, Optional

from langchain_core.tools import tool

from app.agents.rag import get_rag
from app.contracts.schemas import SevenFieldExtraction
from app.core.comparator import compare_seven_fields
from app.core.policy import explain_policy, merged_policy


@tool
def compare_si_bl(si_extraction: dict[str, Any], bl_extraction: dict[str, Any], confidence_threshold: float = 0.85) -> dict[str, Any]:
    """Deterministically compare the seven fields of a Shipping Instruction against a Draft BL. SI is the source of truth.
    Returns comparison_status, mismatch_count, message and per-field results. This is the ONLY way a mismatch can be decided."""
    res = compare_seven_fields(SevenFieldExtraction(**si_extraction), SevenFieldExtraction(**bl_extraction), confidence_threshold=confidence_threshold)
    return res.model_dump(mode="json")


@tool
def lookup_policy(section: Optional[str] = None) -> dict[str, Any]:
    """Return the active verification/communication/security policy (optionally one section) as human-readable lines."""
    from app.config import get_repo

    pol = merged_policy(get_repo().get_active_policy().values)
    if section and section in pol:
        return {section: pol[section]}
    return {"explanation": explain_policy(pol), "policy": pol}


@tool
def search_knowledge(query: str, case_id: Optional[str] = None, k: int = 5) -> list[dict[str, Any]]:
    """Semantic search over the policy/glossary/port knowledge base and (if case_id is given) that case's own email, documents and comparison. Never returns other cases."""
    hits = get_rag().search(query, case_id=case_id, k=k)
    return [{"id": h["id"], "source": h["source"], "score": h["score"], "text": h["text"][:600]} for h in hits]


TOOLS = [compare_si_bl, lookup_policy, search_knowledge]
