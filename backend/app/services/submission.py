"""Map a CaseRecord to the SDOC hackathon submission row (external contract)."""
from __future__ import annotations

from app.contracts.schemas import CaseRecord, EmailMessage, HackathonCategory, HackathonSubmissionRow


def case_to_submission_row(case: CaseRecord, email: EmailMessage) -> HackathonSubmissionRow:
    cmp = case.comparison
    category = case.hackathon_category
    if category == HackathonCategory.BL_COMPARISON:
        if case.review_reason is not None:
            status = "NEEDS_REVIEW"
        elif cmp is not None and cmp.mismatch_count > 0:
            status = "MISMATCH"
        else:
            status = "OK"
    else:
        status = "OK"
    has_defect = status == "MISMATCH"
    return HackathonSubmissionRow(
        category=category,
        status=status,
        review_reason=case.review_reason if status == "NEEDS_REVIEW" else None,
        defect_fields=list(cmp.mismatch_fields) if (cmp and has_defect) else [],
        has_defect=has_defect,
        decided_by=case.classification.decided_by,
    )
