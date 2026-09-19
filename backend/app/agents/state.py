"""
LangGraph state for the NovaShip case graph.

One GraphState per case (thread_id = case id). Nodes read/write only the keys
they own. Rich objects are stored as plain dicts (JSON-safe for checkpoints).
"""
from __future__ import annotations

from typing import Any, Optional, TypedDict


class HumanDecision(TypedDict, total=False):
    action: str            # approve | edit | reject | reassign | notify_party | retry | complete | mark_no_action
    draft_id: Optional[str]
    edited_subject: Optional[str]
    edited_body: Optional[str]
    note: Optional[str]
    user_id: str
    recipient: Optional[dict[str, Any]]   # {recipient_type, recipient_user_id|recipient_party_id, include_fields, due_date}


class GraphState(TypedDict, total=False):
    # ---- identity
    case_id: str
    email_id: str
    actor_id: str

    # ---- node outputs (dict form of the frozen contracts)
    security: dict[str, Any]          # SecurityAssessment
    security_agent: dict[str, Any]    # LLM/rule security agent verdict + reasoning
    classification: dict[str, Any]    # IntentClassification
    attachments: list[dict[str, Any]] # AttachmentClassification[]
    si_extraction: Optional[dict[str, Any]]
    bl_extraction: Optional[dict[str, Any]]
    comparison: Optional[dict[str, Any]]  # ComparisonResult (deterministic tool)
    review_reason: Optional[str]
    recommendation: Optional[dict[str, Any]]
    summary: Optional[dict[str, Any]]
    draft: Optional[dict[str, Any]]
    rag_context: list[dict[str, Any]]  # retrieved policy/glossary/case chunks

    # ---- control flow
    route: str                        # security_review | no_action | verification | other
    status: str                       # CaseStatus literal
    needs_human: bool
    human_decision: Optional[HumanDecision]
    notified: bool
    errors: list[dict[str, Any]]
    trace: list[dict[str, Any]]       # DecisionTrace-like entries appended by each node
