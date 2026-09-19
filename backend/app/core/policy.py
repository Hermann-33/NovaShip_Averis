"""
Policy evaluator - admin-configurable, versioned rules.

Deterministic. Every change to the active policy creates a new version row and
an audit event (see services/policy_service.py).
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

DEFAULT_POLICY: dict[str, Any] = {
    "verification": {
        "source_of_truth": "SI",
        "required_fields": [
            "shipper", "consignee", "notify_party", "port_of_loading",
            "port_of_discharge", "container_count", "gross_weight_kg",
        ],
        "weight_unit": "kg",
        "field_confidence_threshold": 0.85,
        "legal_name_normalization": "casefold_whitespace_only",
        "port_alias_policy": "strip_unlocode_only",
    },
    "human_review": {
        "confidence_below": 0.85,
        "missing_required_field": True,
        "external_recipient_requires_approval": True,
        "suspicious_sender_to_security_review": True,
    },
    "communication": {
        "auto_send_external": False,
        "external_drafts_require_confirmation": True,
        "internal_share_roles": ["OPERATIONS_STAFF", "SUPERVISOR", "ADMIN"],
        "external_notify_roles": ["SUPERVISOR", "ADMIN"],
    },
    "security": {
        "blocked_attachment_types": [".exe", ".bat", ".cmd", ".js", ".vbs", ".scr", ".msi", ".ps1", ".jar"],
        "suspicious_domain_words": ["prize", "claim", "verify", "parcel", "crypto", "invest"],
        "max_attachments": 10,
        "duplicate_window_hours": 72,
        "trusted_domains": ["aprilasia.com", "april.com.my"],
        "partner_domains": ["fujitogrp.com", "safqa.co.ke", "psabdp.com", "roxcel.at", "ifpla.com", "algurg.ae", "vitalsolutions.sg"],
    },
    "intent": {"intent_llm_threshold": 0.75},
}


def merged_policy(overrides: dict[str, Any] | None) -> dict[str, Any]:
    base = deepcopy(DEFAULT_POLICY)
    for section, values in (overrides or {}).items():
        if isinstance(values, dict) and isinstance(base.get(section), dict):
            base[section].update(values)
        else:
            base[section] = values
    return base


def flat_security(policy: dict[str, Any]) -> dict[str, Any]:
    sec = dict(policy.get("security", {}))
    return sec


def confidence_threshold(policy: dict[str, Any]) -> float:
    return float(policy.get("verification", {}).get("field_confidence_threshold", 0.85))


def explain_policy(policy: dict[str, Any]) -> list[str]:
    """Human-readable policy explanation used by the assistant and admin UI."""
    v, h, c, s = policy["verification"], policy["human_review"], policy["communication"], policy["security"]
    return [
        f"The Shipping Instruction ({v['source_of_truth']}) is always the source of truth.",
        f"Exactly {len(v['required_fields'])} fields are compared: " + ", ".join(v["required_fields"]) + ".",
        f"Weights are compared in {v['weight_unit']}; names are normalised by {v['legal_name_normalization'].replace('_', ' ')} (no legal-name rewriting).",
        f"Any field extracted with confidence below {h['confidence_below']:.2f} or missing is routed to HUMAN_REVIEW instead of being decided.",
        "External email is never auto-sent: " + ("every external draft requires human confirmation." if c["external_drafts_require_confirmation"] else "confirmation is optional."),
        f"Only roles {', '.join(c['external_notify_roles'])} may notify an external party; {', '.join(c['internal_share_roles'])} may share internally.",
        f"Blocked attachment types: {', '.join(s['blocked_attachment_types'])}. Max attachments per email: {s['max_attachments']}.",
    ]
