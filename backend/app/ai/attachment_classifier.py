"""
Node 3 - Attachment / document-type classifier.

Decides SI vs Draft BL vs Invoice vs Supporting vs Unknown from CONTENT first
(title lines, distinctive fields), then file-name hints. Confidence reflects
how much evidence agreed.
"""
from __future__ import annotations

import re

from app.contracts.schemas import AttachmentClassification, AttachmentMeta, DocumentType, ExtractionStatus

TITLE_RULES: list[tuple[DocumentType, list[str], float]] = [
    (DocumentType.INVOICE, [r"^\s*COMMERCIAL INVOICE", r"THIS IS A COMMERCIAL INVOICE", r"^\s*INVOICE\b", r"Total Amount:\s*USD"], 0.95),
    (DocumentType.SUPPORTING_DOCUMENT, [r"^\s*PACKING LIST", r"PACKING LIST ONLY", r"^\s*CERTIFICATE OF ORIGIN", r"NOT AN SI OR BL"], 0.95),
    (DocumentType.SHIPPING_INSTRUCTION, [r"^\s*SHIPPING INSTRUCTION", r"BILL OF LADING INSTRUCTION", r"\bBL INSTRUCTION\b", r"\[\[SHEET S\.I\.\]\]"], 0.9),
    (DocumentType.DRAFT_BL, [r"BILL OF LADING\s*\(DRAFT\)", r"^\s*BILL OF LADING\b", r"提单号", r"\[\[SHEET BL\]\]", r"Bill of Lading No\.", r"B/L No\.", r"B/L NUMBER"], 0.9),
]

FILENAME_HINTS = {
    DocumentType.SHIPPING_INSTRUCTION: [r"_SI\b", r"\bSI[_\-\.]", r"shipping[_ ]?instruction"],
    DocumentType.DRAFT_BL: [r"_BL\b", r"\bBL[_\-\.]", r"draft[_ ]?bl", r"bill[_ ]?of[_ ]?lading"],
    DocumentType.INVOICE: [r"invoice", r"\binv\b"],
    DocumentType.SUPPORTING_DOCUMENT: [r"packing", r"coo", r"certificate"],
}


def classify_attachment(att: AttachmentMeta, text: str | None) -> AttachmentClassification:
    text = text or ""
    scores: dict[DocumentType, float] = {d: 0.0 for d in DocumentType}
    why: list[str] = []

    for doc_type, pats, w in TITLE_RULES:
        for p in pats:
            if re.search(p, text, re.I | re.M):
                scores[doc_type] += w
                why.append(f"content matches /{p}/")
                break

    # SI vs BL disambiguation: a BL carries a B/L number; an SI carries a booking/OC ref
    if re.search(r"(Bill of Lading No\.|B/L No\.|BL No\.|B/L NUMBER|提单号)", text, re.I):
        scores[DocumentType.DRAFT_BL] += 0.3
    if re.search(r"OC No\.|Booking (Ref|No\.|Reference)", text, re.I) and not re.search(r"BILL OF LADING", text, re.I):
        scores[DocumentType.SHIPPING_INSTRUCTION] += 0.2

    for doc_type, pats in FILENAME_HINTS.items():
        for p in pats:
            if re.search(p, att.file_name, re.I):
                scores[doc_type] += 0.35
                why.append(f"file name hints {doc_type.value}")
                break

    best = max(scores, key=lambda d: scores[d])
    best_score = scores[best]
    if best_score == 0:
        best = DocumentType.UNKNOWN_DOCUMENT
    conf = min(0.99, 0.4 + best_score * 0.45) if best_score else 0.3

    # unreadable / empty -> the type is at best a filename guess
    if att.extraction_status in (ExtractionStatus.UNREADABLE, ExtractionStatus.EMPTY, ExtractionStatus.UNSUPPORTED):
        conf = min(conf, 0.5)
        why.append(f"content unavailable ({att.extraction_status.value}); type inferred from file name only")

    return AttachmentClassification(
        attachment_id=att.id, file_name=att.file_name, file_type=att.file_type,
        detected_type=best, confidence=round(conf, 2), rationale="; ".join(why[:3]) or "no signals",
        extraction_status=att.extraction_status,
    )
