# P4 handoff: evidence semantics

Use the following contract when rendering extracted values and seven-field comparisons.

| Property | Meaning | Frontend treatment |
|---|---|---|
| `evidence.document_id` | The attachment ID, not the case ID and not the filename | Use it to link evidence to the attachment record/download |
| `evidence.line` | One-based line number in the reader's extracted text | Display directly; do not add or subtract one |
| `evidence.page` | Current page number taken from a `[[PAGE n]]` marker inserted by the PDF reader | Display only when non-null; TXT, DOCX, and XLSX may have no meaningful page |
| `evidence.snippet` | Literal source evidence, truncated by the extractor to 200 characters | Show verbatim and escape as text; do not treat it as HTML |
| `evidence.label_found` | Exact synonym that matched the source, or `(llm)` for a verified LLM fallback | Show this separately from the canonical field label |

For each comparison field, `si_evidence` and `bl_evidence` follow the same contract. `original` is the extracted document text and should be used in the evidence view. `normalized` exists only for safe deterministic comparison; it must not replace the original value in the source display.

Important behaviour:

- Evidence explains where a value came from; it is not itself the MATCH/MISMATCH verdict.
- A missing value has empty evidence and must be shown as requiring review, not as a mismatch.
- An unreadable or wrong-type document has no valid comparison evidence and must route to human review.
- PDF page numbers originate only from `[[PAGE n]]`; never infer a page from line count.
- The Notify Party value is comparison data, not permission to contact that party. External notification still requires an approved contact and Supervisor/Admin confirmation.

Example:

```json
{
  "original": "PORT KLANG (MYPKG)",
  "normalized": "port klang",
  "evidence": {
    "document_id": "att_email_004_si",
    "page": 1,
    "line": 12,
    "snippet": "Port of Loading (POL): PORT KLANG (MYPKG)",
    "label_found": "Port of Loading (POL)"
  }
}
```

