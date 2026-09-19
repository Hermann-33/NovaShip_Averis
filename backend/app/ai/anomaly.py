"""Unusual-behaviour detection (evidence-based, never accusatory)."""
from __future__ import annotations

from typing import Optional

from app.contracts.schemas import (
    AttachmentMeta,
    ComparisonResult,
    DocumentType,
    EmailMessage,
    ExtractionStatus,
    FieldResult,
    SecuritySignal,
)


def detect_anomalies(
    email: EmailMessage,
    attachments: list[AttachmentMeta],
    comparison: Optional[ComparisonResult],
    sender_history_count: int = 0,
    failed_extraction_count: int = 0,
) -> list[SecuritySignal]:
    out: list[SecuritySignal] = []
    types = [a.detected_type for a in attachments]
    if DocumentType.INVOICE in types or DocumentType.SUPPORTING_DOCUMENT in types:
        names = [a.file_name for a in attachments if a.detected_type in (DocumentType.INVOICE, DocumentType.SUPPORTING_DOCUMENT)]
        out.append(SecuritySignal(signal="UNEXPECTED_DOCUMENT_TYPE", severity="MEDIUM",
                                  evidence=f"Attachment(s) {', '.join(names)} are not an SI/Draft BL although a verification was requested.",
                                  recommended_action="Ask the sender for the correct Draft BL."))
    if len([a for a in attachments if a.detected_type == DocumentType.DRAFT_BL]) > 1:
        out.append(SecuritySignal(signal="CONFLICTING_VERSIONS", severity="MEDIUM",
                                  evidence="More than one Draft BL attached to the same request.",
                                  recommended_action="Confirm which version is current before comparing."))
    dup = [a for a in attachments if a.is_duplicate_of]
    if dup:
        out.append(SecuritySignal(signal="DUPLICATE_DOCUMENT", severity="LOW",
                                  evidence=f"{len(dup)} attachment(s) byte-identical to earlier documents.",
                                  recommended_action="Link the existing document; avoid double processing."))
    if len(attachments) > 6:
        out.append(SecuritySignal(signal="MANY_ATTACHMENTS", severity="LOW",
                                  evidence=f"{len(attachments)} attachments on one message.",
                                  recommended_action="Verify all are relevant before processing."))
    if failed_extraction_count >= 2:
        out.append(SecuritySignal(signal="REPEATED_FAILED_EXTRACTION", severity="MEDIUM",
                                  evidence=f"{failed_extraction_count} extraction failures for this sender/thread.",
                                  recommended_action="Ask the sender for text-readable documents."))
    if comparison:
        for f in comparison.fields:
            if f.result == FieldResult.MISMATCH and f.field == "gross_weight_kg" and f.si_normalized and f.bl_normalized:
                try:
                    diff = abs(float(f.si_normalized) - float(f.bl_normalized)) / max(1.0, float(f.si_normalized))
                except (TypeError, ValueError):
                    continue
                if diff > 0.25:
                    out.append(SecuritySignal(signal="EXTREME_VALUE_DIFFERENCE", severity="HIGH",
                                              evidence=f"Gross weight differs by {diff:.0%} (SI {f.si_original} vs BL {f.bl_original}).",
                                              recommended_action="Verify with the shipper before requesting a correction."))
            if f.result == FieldResult.MISMATCH and f.field == "container_count" and f.si_normalized and f.bl_normalized:
                if abs(int(f.si_normalized) - int(f.bl_normalized)) >= 3:
                    out.append(SecuritySignal(signal="EXTREME_VALUE_DIFFERENCE", severity="HIGH",
                                              evidence=f"Container count differs by {abs(int(f.si_normalized) - int(f.bl_normalized))} (SI {f.si_original} vs BL {f.bl_original}).",
                                              recommended_action="Verify the booking with the carrier."))
    if any(a.extraction_status in (ExtractionStatus.UNREADABLE, ExtractionStatus.EMPTY) for a in attachments):
        out.append(SecuritySignal(signal="UNREADABLE_ATTACHMENT", severity="MEDIUM",
                                  evidence="At least one attachment has no readable text layer or is empty/corrupt.",
                                  recommended_action="Request a readable copy or run OCR."))
    return out
