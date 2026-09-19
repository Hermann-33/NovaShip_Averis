#!/usr/bin/env python3
"""
Generate Supabase seed data for ALL tables from the SDOC bundle.

    cd backend
    python -m app.seed.make_seed                    # -> ../supabase/seed/seed.sql + tables/*.json + snapshot.json
    python -m app.seed.make_seed --limit 50         # smaller seed for a quick demo
    python -m app.seed.make_seed --push             # also upsert into Supabase via REST (needs SUPABASE_URL + SERVICE key)

Outputs
  supabase/seed/seed.sql          one transaction, idempotent (ON CONFLICT DO UPDATE)
  supabase/seed/tables/<t>.json   row arrays per table (for the Table Editor "Import" or scripts)
  supabase/seed/snapshot.json     rich snapshot loaded by the API in memory mode (REPO_BACKEND=memory)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from app.contracts.schemas import SEVEN_FIELDS  # noqa: E402
from app.pipeline.orchestrator import Pipeline  # noqa: E402
from app.repositories.memory import DEFAULT_PARTIES, DEFAULT_TEAMS, DEFAULT_USERS, MemoryRepository  # noqa: E402

TENANT = os.environ.get("TENANT_ID", "tenant_april")
ROLES = [("OPERATIONS_STAFF", "Handles cases, drafts, internal shares"), ("SUPERVISOR", "Approves external sends, notifies parties"),
         ("ADMIN", "Edits policy, manages users"), ("AUDITOR", "Read-only access incl. audit history")]


def sql_val(v: Any) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, (dict, list)):
        return "'" + json.dumps(v, ensure_ascii=False, default=str).replace("'", "''") + "'::jsonb"
    if isinstance(v, datetime):
        return "'" + v.isoformat() + "'"
    return "'" + str(v).replace("'", "''") + "'"


def upsert(table: str, rows: list[dict[str, Any]], pk: str = "id") -> str:
    if not rows:
        return f"-- {table}: no rows\n"
    cols = list(rows[0].keys())
    out = [f"-- {table}: {len(rows)} rows"]
    chunk = 200
    for i in range(0, len(rows), chunk):
        vals = ",\n".join("(" + ", ".join(sql_val(r.get(c)) for c in cols) + ")" for r in rows[i:i + chunk])
        upd = ", ".join(f"{c} = excluded.{c}" for c in cols if c != pk)
        conflict = f"on conflict ({pk}) do update set {upd}" if upd else f"on conflict ({pk}) do nothing"
        out.append(f"insert into {table} ({', '.join(cols)}) values\n{vals}\n{conflict};")
    return "\n".join(out) + "\n"


def build_tables(repo: MemoryRepository, base_time: datetime) -> dict[str, list[dict[str, Any]]]:
    T: dict[str, list[dict[str, Any]]] = {k: [] for k in [
        "tenants", "teams", "roles", "users", "user_roles", "party_contacts", "email_messages", "attachments", "cases", "case_documents",
        "extracted_fields", "comparisons", "comparison_fields", "case_summaries", "action_recommendations", "drafts", "assignments", "shares",
        "notifications", "policies", "policy_versions", "audit_events", "processing_errors", "ai_runs"]}
    T["tenants"].append({"id": TENANT, "name": "APRIL Fine Paper Trading (demo tenant)", "created_at": base_time})
    for t in DEFAULT_TEAMS:
        T["teams"].append({"id": t["id"], "tenant_id": TENANT, "name": t["name"]})
    for rid, desc in ROLES:
        T["roles"].append({"id": rid, "description": desc})
    for u in DEFAULT_USERS:
        T["users"].append({"id": u.id, "tenant_id": TENANT, "email": u.email, "display_name": u.display_name, "team_id": u.team_id, "is_external": u.is_external, "created_at": base_time})
        for r in u.roles:
            T["user_roles"].append({"user_id": u.id, "role_id": r.value})
    for p in DEFAULT_PARTIES:
        T["party_contacts"].append({"id": p.id, "tenant_id": TENANT, "name": p.name, "email": p.email, "party_name": p.party_name, "approved": p.approved})

    for e in repo.list_emails():
        T["email_messages"].append({"id": e.id, "tenant_id": TENANT, "provider": e.provider, "provider_message_id": e.provider_message_id, "conversation_id": e.conversation_id,
                                    "sender": e.sender, "sender_name": e.sender_name, "recipients": e.recipients, "cc": e.cc, "subject": e.subject, "body": e.body,
                                    "received_at": e.received_at, "language": e.language, "checksum": e.checksum, "is_duplicate_of": e.is_duplicate_of,
                                    "payload": json.loads(e.model_dump_json()), "created_at": e.received_at})
        for a in e.attachments:
            T["attachments"].append({"id": a.id, "tenant_id": TENANT, "source_email_id": e.id, "file_name": a.file_name, "file_type": a.file_type, "size_bytes": a.size_bytes,
                                     "checksum": a.checksum, "storage_pointer": a.storage_pointer, "detected_type": a.detected_type.value, "detection_confidence": a.detection_confidence,
                                     "extraction_status": a.extraction_status.value, "extraction_confidence": a.extraction_confidence, "raw_text": a.raw_text, "page_count": a.page_count,
                                     "is_duplicate_of": a.is_duplicate_of})

    for c in repo.list_cases():
        T["cases"].append({"id": c.id, "tenant_id": TENANT, "source_email_id": c.source_email_id, "intent": c.intent.value, "hackathon_category": c.hackathon_category.value,
                           "action_required": c.action_required, "priority": c.priority.value, "status": c.status.value, "security_outcome": c.security.outcome.value,
                           "mismatch_count": c.mismatch_count, "comparison_status": c.comparison_status.value if c.comparison_status else None,
                           "review_reason": c.review_reason.value if c.review_reason else None, "confidence": c.confidence, "si_available": c.si_available, "bl_available": c.bl_available,
                           "si_document_id": c.si_document_id, "bl_document_id": c.bl_document_id, "assigned_user_id": c.assigned_user_id, "assigned_team_id": c.assigned_team_id,
                           "shared_with": c.shared_with, "processing_ms": c.processing_ms, "payload": json.loads(c.model_dump_json()), "created_at": c.created_at, "updated_at": c.updated_at})
        if c.si_document_id:
            T["case_documents"].append({"id": f"cd_{c.id}_SI", "case_id": c.id, "attachment_id": c.si_document_id, "role": "SI"})
        if c.bl_document_id:
            T["case_documents"].append({"id": f"cd_{c.id}_BL", "case_id": c.id, "attachment_id": c.bl_document_id, "role": "BL"})
        for kind, ext in (("SI", c.si_extraction), ("BL", c.bl_extraction)):
            if ext:
                for f in SEVEN_FIELDS:
                    x = ext.get(f)
                    T["extracted_fields"].append({"id": f"xf_{c.id}_{kind}_{f}", "tenant_id": TENANT, "case_id": c.id, "document_kind": kind, "field_name": f, "original_value": x.original,
                                                  "normalized_value": None if x.normalized is None else str(x.normalized), "confidence": x.confidence, "needs_review": x.needs_review,
                                                  "evidence": json.loads(x.evidence.model_dump_json())})
        if c.comparison:
            cmp = c.comparison
            T["comparisons"].append({"id": f"cmp_{c.id}", "tenant_id": TENANT, "case_id": c.id, "comparison_status": cmp.comparison_status.value, "mismatch_count": cmp.mismatch_count,
                                     "required_field_count": cmp.required_field_count, "message": cmp.message, "mismatch_fields": cmp.mismatch_fields, "review_fields": cmp.review_fields,
                                     "review_reason": cmp.review_reason.value if cmp.review_reason else None, "compared_at": cmp.compared_at, "si_document_id": cmp.si_document_id,
                                     "bl_document_id": cmp.bl_document_id, "policy_version": cmp.policy_version})
            for f in cmp.fields:
                T["comparison_fields"].append({"id": f"cf_{c.id}_{f.field}", "comparison_id": f"cmp_{c.id}", "case_id": c.id, "tenant_id": TENANT, "field_name": f.field,
                                               "si_original": f.si_original, "bl_original": f.bl_original, "si_normalized": None if f.si_normalized is None else str(f.si_normalized),
                                               "bl_normalized": None if f.bl_normalized is None else str(f.bl_normalized), "result": f.result.value, "confidence": f.confidence,
                                               "reason": f.reason, "attention": f.attention, "si_evidence": json.loads(f.si_evidence.model_dump_json()), "bl_evidence": json.loads(f.bl_evidence.model_dump_json())})
        if c.summary:
            T["case_summaries"].append({"id": f"sum_{c.id}", "tenant_id": TENANT, "case_id": c.id, "text": c.summary.text, "generated_by": c.summary.generated_by,
                                        "evidence_refs": c.summary.evidence_refs, "confidence": c.summary.confidence})
        if c.recommendation:
            r = c.recommendation
            T["action_recommendations"].append({"id": f"rec_{c.id}", "tenant_id": TENANT, "case_id": c.id, "action_required": r.action_required, "action_type": r.action_type.value,
                                                "priority": r.priority.value, "reason": r.reason, "recommended_action": r.recommended_action, "responsible_role": r.responsible_role.value, "confidence": r.confidence})
        for d in c.drafts:
            T["drafts"].append({"id": d.id, "tenant_id": TENANT, "case_id": c.id, "draft_type": d.draft_type, "to_recipients": d.to, "cc_recipients": d.cc, "subject": d.subject, "body": d.body,
                                "evidence_refs": d.evidence_refs, "status": d.status.value, "version": d.version, "requires_external_approval": d.requires_external_approval,
                                "generated_by": d.generated_by, "created_at": c.created_at})
        if c.assigned_user_id or c.assigned_team_id:
            T["assignments"].append({"id": f"asg_{c.id}", "tenant_id": TENANT, "case_id": c.id, "assigned_user_id": c.assigned_user_id, "assigned_team_id": c.assigned_team_id, "assigned_at": c.updated_at})
        for err in c.errors:
            T["processing_errors"].append({"id": err.id, "tenant_id": TENANT, "case_id": c.id, "category": err.category.value, "step": err.step, "message": err.message,
                                           "safe_details": err.safe_details, "recovery": err.recovery, "retryable": err.retryable, "created_at": err.created_at, "resolved": err.resolved})
        T["ai_runs"].append({"id": f"run:{repo.get_email(c.source_email_id).checksum}", "tenant_id": TENANT, "result": {"case_id": c.id, "status": c.status.value}, "provider": "rules",
                             "model": "deterministic-v1", "latency_ms": c.processing_ms, "created_at": c.created_at})

    for s in repo.list_shares():
        T["shares"].append({**json.loads(s.model_dump_json()), "tenant_id": TENANT})
        T["notifications"].append({"id": f"ntf_{s.id}", "tenant_id": TENANT, "case_id": s.case_id, "channel": "email" if s.is_external else "in_app", "recipient": s.recipient_label,
                                   "subject": f"Case update {s.case_id}", "body": s.message, "status": "SENT" if s.status == "SENT" else "QUEUED", "sent_at": s.sent_at, "created_at": s.sent_at or base_time})

    for p in repo.list_policy_versions():
        T["policy_versions"].append({"id": p.id, "tenant_id": TENANT, "policy_id": "policy_active", "version": p.version, "name": p.name, "values": p.values, "updated_by": p.updated_by,
                                     "change_note": p.change_note, "created_at": p.updated_at})
    T["policies"].append({"id": "policy_active", "tenant_id": TENANT, "name": "default", "active_version": repo.get_active_policy().version})

    for a in repo.list_audit():
        T["audit_events"].append({**json.loads(a.model_dump_json()), "tenant_id": TENANT})
    return T


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", default=str(ROOT / "sdoc-hackathon-bundle"))
    ap.add_argument("--out", default=str(ROOT / "supabase" / "seed"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--push", action="store_true", help="Upsert rows into Supabase via REST (SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY)")
    ap.add_argument("--demo-actions", action="store_true", default=True, help="Add a few assignments/shares/approvals so the dashboard shows the full workflow")
    args = ap.parse_args()

    bundle = Path(args.bundle)
    out = Path(args.out)
    (out / "tables").mkdir(parents=True, exist_ok=True)
    repo = MemoryRepository()
    pipe = Pipeline(repo)
    base_time = datetime(2026, 1, 5, 8, 0, 0)
    files = sorted((bundle / "inbox").glob("email_*.json"))
    if args.limit:
        files = files[: args.limit]
    for i, p in enumerate(files):
        raw = json.loads(p.read_text(encoding="utf-8"))
        blobs = {a: (bundle / a).read_bytes() for a in raw.get("attachments", []) if (bundle / a).exists()}
        email = pipe.ingest_email(raw, blobs, received_at=base_time + timedelta(minutes=17 * i))
        case = pipe.run(email)
        case.created_at = email.received_at
        case.updated_at = email.received_at + timedelta(seconds=45)
        repo.save_case(case)

    if args.demo_actions:
        _demo_actions(repo)

    T = build_tables(repo, base_time)
    sql = ["-- NovaShip Averis seed (generated by backend/app/seed/make_seed.py)", f"-- generated {datetime.utcnow().isoformat()}Z from {len(files)} bundle emails", "begin;",
           "alter table audit_events disable trigger trg_audit_no_update;"]
    for name, rows in T.items():
        pk = "user_id, role_id" if name == "user_roles" else ("event_id" if name == "audit_events" else "id")
        sql.append(upsert(name, rows, pk))
        (out / "tables" / f"{name}.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    sql += ["alter table audit_events enable trigger trg_audit_no_update;", "commit;"]
    (out / "seed.sql").write_text("\n".join(sql), encoding="utf-8")
    repo.save_file(out / "snapshot.json")
    print(f"seed written -> {out}")
    for name, rows in T.items():
        print(f"  {name:24s} {len(rows):6d}")

    if args.push:
        _push(T)
    return 0


def _demo_actions(repo: MemoryRepository) -> None:
    """Exercise the human workflow on a few cases so the seed shows assignments, shares, approvals and completions."""
    from app.contracts.schemas import AssignRequest, DraftDecision, RecipientType, ShareRequest
    from app.services.case_service import CaseService

    svc = CaseService(repo)
    sup = repo.get_user("u_sup_1")
    ops = repo.get_user("u_ops_1")
    mism = [c for c in repo.list_cases() if c.mismatch_count > 0][:6]
    clean = [c for c in repo.list_cases() if c.comparison and c.mismatch_count == 0 and not c.comparison.review_fields][:4]
    for i, c in enumerate(mism):
        svc.assign(c.id, AssignRequest(user_id=["u_ops_1", "u_ops_2", "u_ops_3"][i % 3], note="Seed assignment"), sup)
    if mism:
        c = mism[0]
        svc.begin_notify_party(c.id, sup)
        svc.share(c.id, ShareRequest(recipient_type=RecipientType.NOTIFY_PARTY_CONTACT, recipient_party_id="p_vital", due_date="2026-01-20", confirm_external=True), sup)
    if len(mism) > 1:
        svc.share(mism[1].id, ShareRequest(recipient_type=RecipientType.INTERNAL_USER, recipient_user_id="u_sup_2", message="Please double-check the consignee."), ops)
    if len(mism) > 2:
        c = repo.get_case(mism[2].id)
        svc.approve_draft(c.id, DraftDecision(draft_id=c.drafts[0].id, note="Approved after review"), sup)
    for c in clean[:2]:
        c = repo.get_case(c.id)
        svc.approve_draft(c.id, DraftDecision(draft_id=c.drafts[0].id), sup)
        svc.complete(c.id, ops, note="Draft BL confirmed")
    info = [c for c in repo.list_cases() if c.status.value == "NO_ACTION_INFO"][:3]
    for c in info:
        svc.complete(c.id, ops, note="No reply needed")


def _push(T: dict[str, list[dict[str, Any]]]) -> None:
    from supabase import create_client

    client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    order = list(T.keys())
    for name in order:
        rows = T[name]
        if not rows:
            continue
        payload = json.loads(json.dumps(rows, default=str))
        for i in range(0, len(payload), 500):
            client.table(name).upsert(payload[i:i + 500]).execute()
        print(f"pushed {name}: {len(rows)}")


if __name__ == "__main__":
    raise SystemExit(main())
