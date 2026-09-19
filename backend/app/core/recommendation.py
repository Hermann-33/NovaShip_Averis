"""Node 7 - Action recommendation (deterministic, policy-driven)."""
from __future__ import annotations

from typing import Optional

from app.contracts.schemas import (
    FIELD_LABELS,
    ActionRecommendation,
    ActionType,
    ComparisonResult,
    ComparisonStatus,
    HackathonCategory,
    Intent,
    IntentClassification,
    Priority,
    ReviewReason,
    Role,
    SecurityAssessment,
    SecurityOutcome,
)


def recommend(
    classification: IntentClassification,
    security: SecurityAssessment,
    comparison: Optional[ComparisonResult],
    review_reason: Optional[ReviewReason],
    si_available: bool,
    bl_available: bool,
    draft_bl_requested: bool = False,
) -> ActionRecommendation:
    if security.outcome == SecurityOutcome.SECURITY_REVIEW:
        return ActionRecommendation(
            action_required=True, action_type=ActionType.SECURITY_REVIEW, priority=Priority.CRITICAL,
            reason=security.rationale, recommended_action="Quarantine and review with the security owner before any processing.",
            responsible_role=Role.SUPERVISOR, confidence=0.9,
        )
    if security.outcome == SecurityOutcome.SPAM or classification.hackathon_category == HackathonCategory.SPAM:
        return ActionRecommendation(
            action_required=False, action_type=ActionType.NO_ACTION_INFORMATION, priority=Priority.LOW,
            reason="Classified as spam by the security precheck.", recommended_action="No reply. Archive; keep for audit.",
            responsible_role=Role.OPERATIONS_STAFF, confidence=classification.confidence,
        )

    intent = classification.intent
    if intent in (Intent.DOCUMENT_VERIFICATION, Intent.DOCUMENT_CORRECTION):
        if draft_bl_requested:
            return ActionRecommendation(
                action_required=True, action_type=ActionType.PROVIDE_DRAFT_BL, priority=Priority.MEDIUM,
                reason="The sender is asking for the draft BL so they can check it; no documents attached yet.",
                recommended_action="Obtain the draft BL from the carrier and send it to the requester. Comparison will run once SI + Draft BL are on file.",
                responsible_role=Role.OPERATIONS_STAFF, confidence=classification.confidence,
            )
        if review_reason == ReviewReason.MISSING_ATTACHMENT or not (si_available and bl_available):
            missing = [n for n, ok in (("Shipping Instruction", si_available), ("Draft BL", bl_available)) if not ok]
            return ActionRecommendation(
                action_required=True, action_type=ActionType.REQUEST_MISSING_DOCUMENT, priority=Priority.MEDIUM,
                reason="Required document(s) missing: " + ", ".join(missing) + ".",
                recommended_action="Request the missing document from the sender or link it from an existing case, then retry.",
                responsible_role=Role.OPERATIONS_STAFF, confidence=0.95,
            )
        if review_reason == ReviewReason.WRONG_DOC_TYPE:
            return ActionRecommendation(
                action_required=True, action_type=ActionType.REQUEST_MISSING_DOCUMENT, priority=Priority.MEDIUM,
                reason="An attachment is not an SI or Draft BL (wrong document type).",
                recommended_action="Ask the sender for the actual Draft BL; do not compare against the wrong document.",
                responsible_role=Role.OPERATIONS_STAFF, confidence=0.9,
            )
        if review_reason == ReviewReason.UNREADABLE:
            return ActionRecommendation(
                action_required=True, action_type=ActionType.HUMAN_REVIEW, priority=Priority.MEDIUM,
                reason="An attachment is unreadable (image-only scan, empty or corrupt file).",
                recommended_action="Run OCR or request a text-readable copy, then retry extraction.",
                responsible_role=Role.OPERATIONS_STAFF, confidence=0.9,
            )
        if comparison is None:
            return ActionRecommendation(
                action_required=True, action_type=ActionType.HUMAN_REVIEW, priority=Priority.MEDIUM,
                reason="Comparison did not complete.", recommended_action="Retry extraction/comparison or review manually.",
                responsible_role=Role.OPERATIONS_STAFF, confidence=0.7,
            )
        if comparison.comparison_status == ComparisonStatus.HUMAN_REVIEW:
            fields = ", ".join(FIELD_LABELS[f] for f in comparison.review_fields)
            return ActionRecommendation(
                action_required=True, action_type=ActionType.HUMAN_REVIEW, priority=Priority.MEDIUM,
                reason=f"Fields could not be decided (missing or low confidence): {fields}.",
                recommended_action="Confirm the missing values with the customer before approving the Draft BL.",
                responsible_role=Role.OPERATIONS_STAFF, confidence=0.9,
            )
        if comparison.mismatch_count > 0:
            fields = ", ".join(FIELD_LABELS[f] for f in comparison.mismatch_fields)
            return ActionRecommendation(
                action_required=True, action_type=ActionType.REQUEST_BL_CORRECTION,
                priority=Priority.HIGH if comparison.mismatch_count == 1 else Priority.CRITICAL,
                reason=f"{comparison.mismatch_count} field(s) differ from the SI: {fields}.",
                recommended_action="Review the mismatch evidence, then approve the correction-request draft to the carrier/forwarder.",
                responsible_role=Role.OPERATIONS_STAFF, confidence=min(f.confidence for f in comparison.fields),
            )
        return ActionRecommendation(
            action_required=True, action_type=ActionType.CONFIRM_DOCUMENTS, priority=Priority.LOW,
            reason="All seven fields match the SI.", recommended_action="Approve the confirmation draft to the requester.",
            responsible_role=Role.OPERATIONS_STAFF, confidence=min(f.confidence for f in comparison.fields),
        )
    if intent == Intent.PREPARE_SHIPPING_INSTRUCTION:
        return ActionRecommendation(
            action_required=True, action_type=ActionType.PREPARE_SI, priority=Priority.MEDIUM,
            reason="Sender provided/requested a Shipping Instruction.", recommended_action="Prepare or forward the SI to the carrier and await the draft BL.",
            responsible_role=Role.OPERATIONS_STAFF, confidence=classification.confidence,
        )
    if intent == Intent.INVOICE_QUERY:
        return ActionRecommendation(
            action_required=True, action_type=ActionType.ANSWER_INVOICE_QUERY, priority=Priority.MEDIUM,
            reason="Billing / charges question.", recommended_action="Route to finance or answer with the invoice breakdown.",
            responsible_role=Role.OPERATIONS_STAFF, confidence=classification.confidence,
        )
    if intent == Intent.UNKNOWN_REVIEW:
        return ActionRecommendation(
            action_required=True, action_type=ActionType.HUMAN_REVIEW, priority=Priority.MEDIUM,
            reason="Intent could not be determined confidently.", recommended_action="Read and categorise manually.",
            responsible_role=Role.OPERATIONS_STAFF, confidence=classification.confidence,
        )
    return ActionRecommendation(
        action_required=False, action_type=ActionType.NO_ACTION_INFORMATION, priority=Priority.LOW,
        reason="Informational message; no reply needed.", recommended_action="Saved, summarised and searchable. No reply needed.",
        responsible_role=Role.OPERATIONS_STAFF, confidence=classification.confidence,
    )
