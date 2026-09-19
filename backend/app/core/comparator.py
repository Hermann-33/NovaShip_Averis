"""
DETERMINISTIC seven-field comparator.

  SI is the source of truth.  Each field is compared independently.
  A mismatch in one field NEVER influences another field's result.
  All seven MATCH  ->  message == "No mismatch detected."

No LLM is involved here - this is pure, testable Python.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.contracts.schemas import (
    FIELD_LABELS,
    NO_MISMATCH_MESSAGE,
    SEVEN_FIELDS,
    ComparisonField,
    ComparisonResult,
    ComparisonStatus,
    Evidence,
    FieldResult,
    ReviewReason,
    SevenFieldExtraction,
)
from app.core.normalizer import normalize_field

ATTENTION = {
    "shipper": "Verify the Shipper on the Draft BL against the SI and request correction.",
    "consignee": "Verify the Consignee on the Draft BL against the SI and request correction.",
    "notify_party": "Verify the Notify Party on the Draft BL against the SI and request correction.",
    "port_of_loading": "Verify the Port of Loading on the Draft BL and request correction.",
    "port_of_discharge": "Verify the Port of Discharge on the Draft BL and request correction.",
    "container_count": "Verify and correct the Draft BL container count.",
    "gross_weight_kg": "Verify and correct the Draft BL gross weight (kg).",
}

DEFAULT_CONFIDENCE_THRESHOLD = 0.85


def _fmt(v) -> Optional[str]:
    return None if v is None else str(v)


def compare_field(
    field: str,
    si: SevenFieldExtraction,
    bl: SevenFieldExtraction,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> ComparisonField:
    s = si.get(field)
    b = bl.get(field)
    label = FIELD_LABELS[field]

    si_norm = s.normalized if s.normalized is not None else normalize_field(field, s.original)
    bl_norm = b.normalized if b.normalized is not None else normalize_field(field, b.original)

    si_ev = s.evidence or Evidence()
    bl_ev = b.evidence or Evidence()

    base = dict(
        field=field,
        label=label,
        si_original=s.original,
        bl_original=b.original,
        si_normalized=si_norm,
        bl_normalized=bl_norm,
        si_evidence=si_ev,
        bl_evidence=bl_ev,
    )

    # --- missing values are NOT mismatches ---------------------------------
    if si_norm is None and bl_norm is None:
        return ComparisonField(
            result=FieldResult.MISSING_IN_SI,
            confidence=0.0,
            reason=f"{label} is missing in both the SI and the Draft BL.",
            attention=f"Obtain the {label} from the customer before comparison can complete.",
            **base,
        )
    if si_norm is None:
        return ComparisonField(
            result=FieldResult.MISSING_IN_SI,
            confidence=max(b.confidence, 0.0),
            reason=f"{label} is blank or unreadable in the SI.",
            attention=f"Confirm the {label} on the Shipping Instruction with the customer.",
            **base,
        )
    if bl_norm is None:
        return ComparisonField(
            result=FieldResult.MISSING_IN_BL,
            confidence=max(s.confidence, 0.0),
            reason=f"{label} is blank or unreadable in the Draft BL.",
            attention=f"Request the carrier to complete the {label} on the Draft BL.",
            **base,
        )

    conf = round(min(s.confidence, b.confidence), 3)

    # --- low confidence extraction -> human review (not a verdict) ----------
    if conf < confidence_threshold:
        return ComparisonField(
            result=FieldResult.LOW_CONFIDENCE_REVIEW,
            confidence=conf,
            reason=f"{label} extraction confidence {conf:.2f} is below the policy threshold {confidence_threshold:.2f}.",
            attention=f"Manually verify the {label} on both documents.",
            **base,
        )

    if si_norm == bl_norm:
        return ComparisonField(
            result=FieldResult.MATCH,
            confidence=conf,
            reason=f"{label} matches after safe normalization.",
            attention="None.",
            **base,
        )

    return ComparisonField(
        result=FieldResult.MISMATCH,
        confidence=conf,
        reason=f"{label} differs: SI = '{s.original}', BL = '{b.original}'.",
        attention=ATTENTION[field],
        **base,
    )


def compare_seven_fields(
    si: SevenFieldExtraction,
    bl: SevenFieldExtraction,
    *,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    si_document_id: Optional[str] = None,
    bl_document_id: Optional[str] = None,
    policy_version: str = "v1",
) -> ComparisonResult:
    fields = [compare_field(f, si, bl, confidence_threshold) for f in SEVEN_FIELDS]

    mismatch_fields = [f.field for f in fields if f.result == FieldResult.MISMATCH]
    review_fields = [
        f.field
        for f in fields
        if f.result in (FieldResult.MISSING_IN_SI, FieldResult.MISSING_IN_BL, FieldResult.LOW_CONFIDENCE_REVIEW)
    ]
    mismatch_count = len(mismatch_fields)

    review_reason: Optional[ReviewReason] = None
    if review_fields:
        # missing values dominate; low-confidence is also "missing_value" for the review axis
        review_reason = ReviewReason.MISSING_VALUE

    if mismatch_count == 0 and not review_fields:
        status = ComparisonStatus.PASSED
        message = NO_MISMATCH_MESSAGE
    elif mismatch_count > 0:
        status = ComparisonStatus.ATTENTION_REQUIRED
        noun = "mismatch" if mismatch_count == 1 else "mismatches"
        message = f"{mismatch_count} {noun} detected: " + ", ".join(FIELD_LABELS[f] for f in mismatch_fields) + "."
        if review_fields:
            message += " " + f"{len(review_fields)} field(s) need human review: " + ", ".join(FIELD_LABELS[f] for f in review_fields) + "."
    else:
        status = ComparisonStatus.HUMAN_REVIEW
        message = "Comparison incomplete: " + ", ".join(FIELD_LABELS[f] for f in review_fields) + " need(s) human review."

    return ComparisonResult(
        comparison_status=status,
        mismatch_count=mismatch_count,
        required_field_count=len(SEVEN_FIELDS),
        message=message,
        fields=fields,
        mismatch_fields=mismatch_fields,
        review_fields=review_fields,
        review_reason=review_reason,
        compared_at=datetime.utcnow(),
        si_document_id=si_document_id,
        bl_document_id=bl_document_id,
        policy_version=policy_version,
    )
