"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, post, FIELD_LABELS, type CaseRow, type Metrics } from "@/lib/api";
import { Badge, Button, Confidence, PRIORITY_COLORS, StatusBadge, Toast, fmtDate } from "@/components/ui";

const STATUSES = ["RECEIVED","SECURITY_REVIEW","CLASSIFIED","NO_ACTION_INFO","WAITING_DOCUMENTS","NO_MISMATCH_DETECTED","MISMATCH_DETECTED","HUMAN_REVIEW","DRAFT_READY","NOTIFY_PARTY","AWAITING_RESPONSE","ASSIGNED","COMPLETED","ERROR"];
const INTENTS = ["DOCUMENT_VERIFICATION","DOCUMENT_CORRECTION","PREPARE_SHIPPING_INSTRUCTION","INVOICE_QUERY","OPERATIONAL_UPDATE","GENERAL_ENQUIRY","INFORMATION_ONLY","NO_ACTION_REQUIRED","UNKNOWN_REVIEW"];
const EMPTY_FILTERS = { status: "", priority: "", intent: "", mismatch: "", assigned: "", shared: "", sender: "", q: "", min_confidence: "", security: "", sort: "updated_desc", date_from: "", date_to: "" };
const STATUS_ORDER = ["RECEIVED","SECURITY_CHECK","SECURITY_REVIEW","CLASSIFIED","NO_ACTION_INFO","DOCUMENTS_DETECTED","WAITING_DOCUMENTS","EXTRACTING","COMPARING","NO_MISMATCH_DETECTED","MISMATCH_DETECTED","HUMAN_REVIEW","DRAFT_READY","NOTIFY_PARTY","AWAITING_RESPONSE","ASSIGNED","COMPLETED","ERROR"];
const STATUS_TONE: Record<string, string> = { HUMAN_REVIEW: "bg-review", MISMATCH_DETECTED: "bg-mismatch", SECURITY_REVIEW: "bg-mismatch", ERROR: "bg-mismatch", WAITING_DOCUMENTS: "bg-review", NO_MISMATCH_DETECTED: "bg-match", COMPLETED: "bg-match", NO_ACTION_INFO: "bg-ink-300" };

export default function Dashboard() {
  const router = useRouter();
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [fields, setFields] = useState<any[]>([]);
  const [attention, setAttention] = useState<CaseRow[] | null>(null);
  const [security, setSecurity] = useState<any[] | null>(null);
  const [activity, setActivity] = useState<any[] | null>(null);
  const [rows, setRows] = useState<CaseRow[] | null>(null);
  const [total, setTotal] = useState(0);
  const [users, setUsers] = useState<any[]>([]);
  const [f, setF] = useState<Record<string, string>>(EMPTY_FILTERS);
  const [page, setPage] = useState(0);
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [toast, setToast] = useState<{ msg: string; kind: "ok" | "err" } | null>(null);
  const [busy, setBusy] = useState(false);
  const [apiDown, setApiDown] = useState(false);
  const limit = 25;

  const say = (msg: string, kind: "ok" | "err" = "ok") => { setToast({ msg, kind }); setTimeout(() => setToast(null), 3500); };

  const load = useCallback(() => {
    const qs = new URLSearchParams({ limit: String(limit), offset: String(page * limit) });
    Object.entries(f).forEach(([k, v]) => v && qs.set(k, v));
    api<{ total: number; items: CaseRow[] }>(`/cases?${qs}`).then((d) => { setRows(d.items); setTotal(d.total); setApiDown(false); }).catch((e) => { setRows([]); setApiDown(true); say(e.message, "err"); });
    api<Metrics>("/dashboard/metrics").then(setMetrics).catch(() => {});
  }, [f, page]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    api("/users").then((d) => setUsers(d.users)).catch(() => {});
    api("/dashboard/fields").then((d) => setFields(d.fields)).catch(() => {});
    api<{ items: CaseRow[] }>("/cases?sort=priority&limit=60").then((d) => setAttention(d.items.filter((r) => r.action_required && !["COMPLETED", "NO_ACTION_INFO", "AWAITING_RESPONSE"].includes(r.status)).slice(0, 7))).catch(() => setAttention([]));
    api("/security/queue").then((d) => setSecurity(d.items)).catch(() => setSecurity([]));
    api("/audit?limit=8").then((d) => setActivity(d.events)).catch(() => setActivity(null)); // hidden for roles without view_audit
  }, []);

  const applyPreset = (patch: Record<string, string>) => { setF({ ...EMPTY_FILTERS, ...patch }); setPage(0); document.getElementById("case-table")?.scrollIntoView({ behavior: "smooth", block: "start" }); };
  const setFilter = (k: string, v: string) => { setF((p) => ({ ...p, [k]: v })); setPage(0); };
  const toggle = (id: string) => setSel((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const batch = async (action: string, params: any = {}, confirm = false) => {
    if (!sel.size) return say("Select cases first", "err");
    setBusy(true);
    try {
      const r = await post("/cases/batch", { action, case_ids: [...sel], params, confirm });
      if (r.requires_confirmation) { if (window.confirm(`${r.note}\n\nProceed with '${action}' on ${r.count} cases?`)) return batch(action, params, true); return; }
      if (action === "export" && r.csv) { const blob = new Blob([r.csv], { type: "text/csv" }); const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "cases.csv"; a.click(); }
      const ok = Object.values(r.results as Record<string, any>).filter((x: any) => x.ok).length;
      say(`${action}: ${ok}/${sel.size} succeeded`); setSel(new Set()); load();
    } catch (e: any) { say(e.message, "err"); } finally { setBusy(false); }
  };
  const quick = async (id: string, path: string, body?: any) => { try { await post(`/cases/${id}${path}`, body); say("Done"); load(); } catch (e: any) { say(e.message, "err"); } };

  const m = metrics;
  const verified = m ? (m.mismatches_detected || 0) + (m.no_mismatch_cases || 0) : 0;
  const mismatchRate = verified ? Math.round(((m?.mismatches_detected || 0) / verified) * 100) : 0;
  type Kpi = { label: string; value: number; tone: string; hint: string; preset: Record<string, string> };
  const kpis = useMemo<Kpi[]>(() => m ? ([
    { label: "Action required", value: m.action_required, tone: "accent", hint: "open cases that need a person", preset: { sort: "priority" } },
    { label: "Mismatches", value: m.mismatches_detected, tone: "mismatch", hint: `${mismatchRate}% of verified pairs`, preset: { mismatch: "yes" } },
    { label: "Human review", value: m.human_review, tone: "review", hint: "waiting for a decision", preset: { status: "HUMAN_REVIEW" } },
    { label: "Waiting for documents", value: m.waiting_for_documents, tone: "review", hint: "SI or Draft BL missing", preset: { status: "WAITING_DOCUMENTS" } },
    { label: "Security flagged", value: m.security_flagged, tone: "mismatch", hint: "spam, suspicious, review", preset: { security: "SPAM" } },
    { label: "No reply needed", value: m.no_action_required, tone: "ink", hint: "filed and searchable", preset: { status: "NO_ACTION_INFO" } },
  ] as Kpi[]) : [], [m, mismatchRate]);

  const statusRows = useMemo(() => {
    if (!m?.by_status) return [];
    const max = Math.max(1, ...Object.values(m.by_status as Record<string, number>));
    return STATUS_ORDER.filter((s) => m.by_status[s]).map((s) => ({ s, n: m.by_status[s] as number, pct: (m.by_status[s] / max) * 100 }));
  }, [m]);
  const intentRows = useMemo(() => {
    if (!m?.by_intent) return [];
    const total = Object.values(m.by_intent as Record<string, number>).reduce((a, b) => a + b, 0) || 1;
    return Object.entries(m.by_intent as Record<string, number>).sort((a, b) => b[1] - a[1]).map(([k, v]) => ({ k, v, pct: (v / total) * 100 }));
  }, [m]);
  const fieldMax = Math.max(1, ...fields.map((x) => x.mismatch));
  const secCounts: Record<string, number> = (security || []).reduce((acc: Record<string, number>, r) => ({ ...acc, [r.outcome]: (acc[r.outcome] || 0) + 1 }), {} as Record<string, number>);

  return (
    <div className="space-y-4">
      {toast && <Toast {...toast} />}

      {/* ---- headline strip -------------------------------------------------- */}
      <section className="overflow-hidden rounded-2xl bg-gradient-to-r from-accent via-[#f26a1b] to-[#fb923c] p-5 text-white shadow-glow">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-orange-100">Operations inbox</div>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight">{m ? `${m.incoming_emails} emails, ${m.action_required} need a person, ${m.mismatches_detected} mismatches found` : apiDown ? "API offline" : "Loading the inbox"}</h1>
            <p className="mt-1 max-w-[70ch] text-sm text-orange-50">SI is the source of truth. Seven fields compared per case. Nothing leaves the mailbox without an approval.</p>
          </div>
          <div className="flex gap-6 text-right">
            <Stat label="Verified pairs" value={verified} />
            <Stat label="Mismatch rate" value={`${mismatchRate}%`} />
            <Stat label="Avg pipeline" value={m ? `${m.avg_processing_ms} ms` : "-"} />
            <Stat label="Completed" value={m?.completed ?? 0} />
          </div>
        </div>
      </section>

      {/* ---- KPI tiles (clickable presets) ----------------------------------- */}
      <section className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6" aria-label="Key metrics">
        {(kpis.length ? kpis : Array.from({ length: 6 }, () => null)).map((k, i) => k ? (
          <button key={k.label} onClick={() => applyPreset(k.preset)} className="group rounded-xl border border-ink-200 bg-white p-3 text-left shadow-card transition hover:-translate-y-[1px] hover:border-accent-ring hover:shadow-glow active:scale-[0.98]">
            <div className="flex items-center justify-between text-[11px] uppercase tracking-wide text-ink-500"><span>{k.label}</span><span className={`h-2 w-2 rounded-full ${k.tone === "accent" ? "bg-accent" : k.tone === "mismatch" ? "bg-mismatch" : k.tone === "review" ? "bg-review" : "bg-ink-300"}`} aria-hidden /></div>
            <div className={`mt-1 text-3xl font-semibold tabular-nums ${k.tone === "accent" ? "text-accent" : k.tone === "mismatch" ? "text-mismatch" : k.tone === "review" ? "text-review-fg" : "text-ink-800"}`}>{k.value}</div>
            <div className="mt-0.5 text-[11px] text-ink-500">{k.hint}</div>
            <div className="mt-1 text-[11px] font-medium text-accent opacity-0 transition group-hover:opacity-100">Show these cases</div>
          </button>
        ) : <div key={i} className="h-[92px] animate-pulse rounded-xl bg-ink-100" aria-busy />)}
      </section>

      {/* ---- analytics row ---------------------------------------------------- */}
      <section className="grid gap-3 lg:grid-cols-3">
        <Panel title="Seven fields, mismatches by field" link={{ href: "/verification", label: "All cases per field" }}>
          {fields.length === 0 ? <Skeleton n={7} /> : (
            <ul className="space-y-1.5">
              {fields.map((x, i) => (
                <li key={x.field}>
                  <Link href="/verification" className="group flex items-center gap-2 text-xs">
                    <span className="w-5 text-ink-400">{i + 1}</span>
                    <span className="w-32 shrink-0 text-ink-700 group-hover:text-accent">{FIELD_LABELS[x.field]}</span>
                    <span className="h-2.5 flex-1 overflow-hidden rounded bg-ink-100"><span className="block h-full rounded bg-gradient-to-r from-accent to-[#fb923c]" style={{ width: `${(x.mismatch / fieldMax) * 100}%` }} /></span>
                    <span className="w-8 text-right font-mono font-semibold text-ink-800">{x.mismatch}</span>
                    <span className="hidden w-16 text-right text-[10px] text-ink-400 sm:inline">{x.review} review</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Where cases are in the workflow" link={{ href: "", label: "" }}>
          {statusRows.length === 0 ? <Skeleton n={7} /> : (
            <ul className="space-y-1.5">
              {statusRows.map((r) => (
                <li key={r.s}>
                  <button onClick={() => applyPreset({ status: r.s })} className="group flex w-full items-center gap-2 text-xs">
                    <span className="w-36 shrink-0 truncate text-left text-ink-700 group-hover:text-accent">{r.s.replace(/_/g, " ").toLowerCase()}</span>
                    <span className="h-2.5 flex-1 overflow-hidden rounded bg-ink-100"><span className={`block h-full rounded ${STATUS_TONE[r.s] || "bg-accent"}`} style={{ width: `${r.pct}%` }} /></span>
                    <span className="w-8 text-right font-mono font-semibold text-ink-800">{r.n}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <div className="grid gap-3">
          <Panel title="What people are asking for" link={{ href: "", label: "" }}>
            {intentRows.length === 0 ? <Skeleton n={4} /> : (
              <div>
                <div className="flex h-3 w-full overflow-hidden rounded-full bg-ink-100" role="img" aria-label="Intent distribution">
                  {intentRows.map((r, i) => <span key={r.k} title={`${r.k} ${r.v}`} style={{ width: `${r.pct}%`, opacity: 1 - i * 0.12 }} className="h-full bg-accent" />)}
                </div>
                <ul className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-[11px]">
                  {intentRows.slice(0, 6).map((r) => <li key={r.k}><button onClick={() => applyPreset({ intent: r.k })} className="flex w-full justify-between hover:text-accent"><span className="truncate text-ink-600">{r.k.replace(/_/g, " ").toLowerCase()}</span><span className="font-mono text-ink-800">{r.v}</span></button></li>)}
                </ul>
              </div>
            )}
          </Panel>
          <Panel title="Security agent" link={{ href: "/security", label: "Open queue" }}>
            {security === null ? <Skeleton n={2} /> : (
              <div className="flex items-center gap-3">
                <Ring value={m ? m.security_flagged : 0} total={m ? m.incoming_emails : 1} />
                <ul className="flex-1 space-y-1 text-[11px]">
                  {[["SECURITY_REVIEW", "bg-mismatch"], ["SUSPICIOUS", "bg-review"], ["SPAM", "bg-ink-400"]].map(([k, c]) => (
                    <li key={k} className="flex items-center gap-2"><span className={`h-2 w-2 rounded-full ${c}`} aria-hidden /><span className="flex-1 text-ink-600">{k.replace("_", " ").toLowerCase()}</span><span className="font-mono font-semibold text-ink-800">{secCounts[k] || 0}</span></li>
                  ))}
                  <li className="pt-1 text-ink-400">attachments are parsed, never executed</li>
                </ul>
              </div>
            )}
          </Panel>
        </div>
      </section>

      {/* ---- attention queue + activity -------------------------------------- */}
      <section className={`grid gap-3 ${activity ? "lg:grid-cols-[2fr_1fr]" : ""}`}>
        <Panel title="Needs your attention now" link={{ href: "", label: "" }} right={<span className="text-[11px] text-ink-500">highest priority first</span>}>
          {attention === null ? <Skeleton n={5} /> : attention.length === 0 ? <div className="rounded-lg border border-dashed border-ink-200 p-5 text-center text-sm text-ink-500">Queue is clear.</div> : (
            <ul className="divide-y divide-ink-100">
              {attention.map((r) => (
                <li key={r.id} className="flex flex-wrap items-center gap-2 py-2 text-xs">
                  <span className={`w-16 font-semibold ${PRIORITY_COLORS[r.priority]}`}>{r.priority}</span>
                  <Link href={`/cases/${r.id}`} className="min-w-0 flex-1 truncate font-medium text-ink-900 hover:text-accent">{r.subject || "(no subject)"}</Link>
                  {r.mismatch_count > 0 ? <Badge className="bg-mismatch text-white">{r.mismatch_count} mismatch</Badge> : r.review_reason ? <Badge className="bg-review-bg text-review-fg">{r.review_reason.replace(/_/g, " ")}</Badge> : <StatusBadge status={r.status} />}
                  <span className="hidden text-ink-500 md:inline">{r.summary.slice(0, 70)}{r.summary.length > 70 ? "…" : ""}</span>
                  <Button kind="primary" onClick={() => router.push(`/cases/${r.id}`)}>Open</Button>
                </li>
              ))}
            </ul>
          )}
        </Panel>
        {activity && (
          <Panel title="Latest activity" link={{ href: "/audit", label: "Full audit" }}>
            <ul className="space-y-1.5 text-[11px]">
              {activity.map((e) => (
                <li key={e.event_id} className="flex gap-2">
                  <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${e.actor_type === "USER" ? "bg-accent" : e.actor_type === "AI" ? "bg-review" : "bg-ink-300"}`} aria-hidden />
                  <div className="min-w-0 flex-1"><span className="font-medium text-ink-800">{e.action.replace(/_/g, " ").toLowerCase()}</span>{e.case_id && <Link href={`/cases/${e.case_id}`} className="ml-1 font-mono text-accent hover:underline">{e.case_id.replace("case_", "")}</Link>}<div className="text-ink-400">{e.actor_type.toLowerCase()} {e.actor_id}, {fmtDate(e.timestamp)}</div></div>
                </li>
              ))}
            </ul>
          </Panel>
        )}
      </section>

      {/* ---- case table --------------------------------------------------------- */}
      <div id="case-table" className="scroll-mt-16 rounded-xl border border-ink-200 bg-white shadow-card">
        <div className="flex flex-wrap items-center gap-2 border-b border-ink-100 px-3 py-2">
          <span className="mr-1 text-sm font-semibold text-ink-800">All cases</span>
          <input placeholder="Search case, subject, sender, summary" value={f.q} onChange={(e) => setFilter("q", e.target.value)} className="w-60 rounded-md border border-ink-200 px-2 py-1.5 text-sm" aria-label="Search" />
          <Sel v={f.status} on={(v) => setFilter("status", v)} opts={STATUSES} ph="Status" />
          <Sel v={f.priority} on={(v) => setFilter("priority", v)} opts={["CRITICAL","HIGH","MEDIUM","LOW"]} ph="Priority" />
          <Sel v={f.intent} on={(v) => setFilter("intent", v)} opts={INTENTS} ph="Intent" />
          <Sel v={f.mismatch} on={(v) => setFilter("mismatch", v)} opts={["yes","no"]} ph="Mismatch" labels={{ yes: "Mismatch", no: "No mismatch" }} />
          <Sel v={f.security} on={(v) => setFilter("security", v)} opts={["SAFE","SPAM","SUSPICIOUS","SECURITY_REVIEW"]} ph="Security" />
          <Sel v={f.assigned} on={(v) => setFilter("assigned", v)} opts={users.map((u) => u.id)} ph="Assigned to" labels={Object.fromEntries(users.map((u) => [u.id, u.display_name]))} />
          <Sel v={f.shared} on={(v) => setFilter("shared", v)} opts={users.map((u) => u.id)} ph="Shared with" labels={Object.fromEntries(users.map((u) => [u.id, u.display_name]))} />
          <input placeholder="Sender" value={f.sender} onChange={(e) => setFilter("sender", e.target.value)} className="w-32 rounded-md border border-ink-200 px-2 py-1.5 text-sm" aria-label="Sender" />
          <input type="number" step="0.05" min="0" max="1" placeholder="Min conf" value={f.min_confidence} onChange={(e) => setFilter("min_confidence", e.target.value)} className="w-24 rounded-md border border-ink-200 px-2 py-1.5 text-sm" aria-label="Minimum confidence" />
          <input type="date" value={f.date_from} onChange={(e) => setFilter("date_from", e.target.value)} className="rounded-md border border-ink-200 px-2 py-1 text-sm" title="Received from" aria-label="Received from" />
          <input type="date" value={f.date_to.slice(0, 10)} onChange={(e) => setFilter("date_to", e.target.value ? e.target.value + "T23:59:59" : "")} className="rounded-md border border-ink-200 px-2 py-1 text-sm" title="Received to" aria-label="Received to" />
          <Sel v={f.sort} on={(v) => setFilter("sort", v)} opts={["updated_desc","received_desc","priority","confidence"]} ph="Sort" labels={{ updated_desc: "Last update", received_desc: "Received", priority: "Priority", confidence: "Confidence, low first" }} />
          <Button kind="ghost" onClick={() => { setF(EMPTY_FILTERS); setPage(0); }}>Clear</Button>
          <span className="ml-auto text-xs text-ink-500">{total} cases</span>
        </div>

        {sel.size > 0 && (
          <div className="flex flex-wrap items-center gap-2 border-b border-ink-100 bg-accent-bg px-3 py-2 text-xs">
            <span className="font-semibold text-accent-fg">{sel.size} selected</span>
            <Button disabled={busy} onClick={() => batch("classify")}>Classify</Button>
            <Button disabled={busy} onClick={() => batch("compare")}>Run comparison</Button>
            <Button disabled={busy} onClick={() => batch("mark_no_action")}>Mark no action</Button>
            <Button disabled={busy} onClick={() => { const u = window.prompt("Assign to user id (e.g. u_ops_1)"); if (u) batch("assign", { user_id: u }); }}>Assign</Button>
            <Button disabled={busy} onClick={() => batch("draft")}>Prepare drafts</Button>
            <Button disabled={busy} onClick={() => batch("request_review")}>Request review</Button>
            <Button disabled={busy} onClick={() => batch("export")}>Export CSV</Button>
            <Button disabled={busy} kind="danger" onClick={() => batch("archive")}>Archive</Button>
            <span className="text-ink-500">External sending is never batched.</span>
          </div>
        )}

        <div className="overflow-x-auto scrollbar-thin">
          <table className="w-full min-w-[1500px] text-left text-xs">
            <thead className="bg-ink-50 text-[11px] uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-2 py-2"><input type="checkbox" aria-label="Select all on page" checked={!!rows?.length && rows.every((r) => sel.has(r.id))} onChange={(e) => setSel(e.target.checked ? new Set((rows || []).map((r) => r.id)) : new Set())} /></th>
                <th className="px-2 py-2">Case</th><th className="px-2 py-2">Subject / sender</th><th className="px-2 py-2">Intent</th><th className="px-2 py-2">Security</th>
                <th className="px-2 py-2">Action</th><th className="px-2 py-2">Priority</th><th className="px-2 py-2">SI / BL</th><th className="px-2 py-2">Mismatch</th>
                <th className="px-2 py-2">Confidence</th><th className="px-2 py-2">Assigned</th><th className="px-2 py-2">Shared</th><th className="px-2 py-2">Status</th><th className="px-2 py-2">Updated</th><th className="px-2 py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows === null && Array.from({ length: 6 }, (_, i) => <tr key={i} className="border-t border-ink-100"><td colSpan={15} className="px-2 py-2"><div className="h-6 animate-pulse rounded bg-ink-100" /></td></tr>)}
              {rows?.map((r) => (
                <tr key={r.id} className={`border-t border-ink-100 align-top hover:bg-accent-bg/30 ${sel.has(r.id) ? "bg-accent-bg/40" : ""}`}>
                  <td className="px-2 py-2"><input type="checkbox" aria-label={`Select ${r.id}`} checked={sel.has(r.id)} onChange={() => toggle(r.id)} /></td>
                  <td className="px-2 py-2 font-mono text-[11px]"><Link href={`/cases/${r.id}`} className="text-accent hover:underline">{r.id.replace("case_", "")}</Link></td>
                  <td className="max-w-[360px] px-2 py-2">
                    <Link href={`/cases/${r.id}`} className="line-clamp-1 font-medium text-ink-900 hover:text-accent">{r.subject || "(no subject)"}</Link>
                    <div className="truncate text-[11px] text-ink-500">{r.sender}</div>
                  </td>
                  <td className="px-2 py-2"><Badge className="bg-ink-100 text-ink-700">{r.intent.replace(/_/g, " ")}</Badge></td>
                  <td className="px-2 py-2"><Badge className={r.security === "SAFE" ? "bg-match-bg text-match-fg" : "bg-mismatch-bg text-mismatch-fg"}>{r.security}</Badge></td>
                  <td className="px-2 py-2">{r.action_required ? <span className="font-semibold text-accent">Required</span> : <span className="text-ink-400">No reply needed</span>}</td>
                  <td className={`px-2 py-2 ${PRIORITY_COLORS[r.priority]}`}>{r.priority}</td>
                  <td className="px-2 py-2 font-mono text-[11px]"><Dot ok={r.si_available} label="SI" /> <Dot ok={r.bl_available} label="BL" /></td>
                  <td className="px-2 py-2">
                    {r.comparison_status === null ? <span className="text-ink-400">-</span> : r.mismatch_count > 0 ? <Badge className="bg-mismatch text-white">{r.mismatch_count} mismatch</Badge> : r.comparison_status === "PASSED" ? <Badge className="bg-match-bg text-match-fg">No mismatch</Badge> : <Badge className="bg-review-bg text-review-fg">Review</Badge>}
                    {r.review_reason && <div className="mt-0.5 text-[10px] text-review-fg">{r.review_reason.replace(/_/g, " ")}</div>}
                  </td>
                  <td className="px-2 py-2"><Confidence value={r.confidence} /></td>
                  <td className="px-2 py-2 text-[11px]">{users.find((u) => u.id === r.assigned_user_id)?.display_name || <span className="text-ink-400">-</span>}</td>
                  <td className="px-2 py-2 text-[11px]">{r.shared_with.length ? `${r.shared_with.length} recipient(s)` : <span className="text-ink-400">-</span>}</td>
                  <td className="px-2 py-2"><StatusBadge status={r.status} />{r.errors > 0 && <div className="mt-0.5 text-[10px] text-mismatch">{r.errors} error(s)</div>}</td>
                  <td className="whitespace-nowrap px-2 py-2 text-[11px] text-ink-500">{fmtDate(r.updated_at)}</td>
                  <td className="px-2 py-2">
                    <div className="flex flex-nowrap gap-1">
                      <Button kind="primary" onClick={() => router.push(`/cases/${r.id}`)}>Open</Button>
                      <Button onClick={() => quick(r.id, "/compare")} title="Re-run extraction and the deterministic comparison">Compare</Button>
                      <Button onClick={() => router.push(`/cases/${r.id}?tab=ask`)}>Ask AI</Button>
                      <Button onClick={() => router.push(`/cases/${r.id}?tab=collab`)}>Share</Button>
                      <Button onClick={() => router.push(`/cases/${r.id}?tab=drafts`)}>Draft</Button>
                      <Button onClick={() => router.push(`/cases/${r.id}?tab=audit`)}>Audit</Button>
                    </div>
                  </td>
                </tr>
              ))}
              {rows?.length === 0 && <tr><td colSpan={15} className="px-4 py-10 text-center text-sm text-ink-500">{apiDown ? "The API is offline. Start the backend on port 8000 and refresh." : "No cases match these filters."}</td></tr>}
            </tbody>
          </table>
        </div>
        <div className="flex items-center justify-between border-t border-ink-100 px-3 py-2 text-xs text-ink-500">
          <span>Page {page + 1} of {Math.max(1, Math.ceil(total / limit))}</span>
          <div className="flex gap-1"><Button disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</Button><Button disabled={(page + 1) * limit >= total} onClick={() => setPage(page + 1)}>Next</Button></div>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return <div><div className="text-2xl font-semibold tabular-nums leading-none">{value}</div><div className="mt-1 text-[11px] uppercase tracking-wide text-orange-100">{label}</div></div>;
}
function Panel({ title, children, link, right }: { title: string; children: React.ReactNode; link: { href: string; label: string }; right?: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-ink-200 bg-white p-4 shadow-card">
      <header className="mb-3 flex items-center justify-between"><h2 className="text-sm font-semibold text-ink-800">{title}</h2>{right}{link.href && link.label && <Link href={link.href} className="text-[11px] font-medium text-accent hover:underline">{link.label}</Link>}</header>
      {children}
    </section>
  );
}
function Skeleton({ n }: { n: number }) { return <div className="space-y-2" aria-busy>{Array.from({ length: n }, (_, i) => <div key={i} className="h-3.5 animate-pulse rounded bg-ink-100" />)}</div>; }
function Ring({ value, total }: { value: number; total: number }) {
  const pct = total ? Math.min(100, Math.round((value / total) * 100)) : 0;
  const r = 26, c = 2 * Math.PI * r;
  return (
    <svg width="72" height="72" viewBox="0 0 72 72" role="img" aria-label={`${pct}% of emails flagged`}>
      <circle cx="36" cy="36" r={r} fill="none" stroke="#f5f5f4" strokeWidth="8" />
      <circle cx="36" cy="36" r={r} fill="none" stroke="#ea580c" strokeWidth="8" strokeDasharray={`${(pct / 100) * c} ${c}`} strokeLinecap="round" transform="rotate(-90 36 36)" />
      <text x="36" y="40" textAnchor="middle" fontSize="13" fontWeight="600" fill="#1c1917">{pct}%</text>
    </svg>
  );
}
function Sel({ v, on, opts, ph, labels }: { v: string; on: (v: string) => void; opts: string[]; ph: string; labels?: Record<string, string> }) {
  return (
    <select value={v} onChange={(e) => on(e.target.value)} aria-label={ph} className="rounded-md border border-ink-200 bg-white px-2 py-1.5 text-sm">
      <option value="">{ph}</option>
      {opts.map((o) => <option key={o} value={o}>{labels?.[o] || o.replace(/_/g, " ")}</option>)}
    </select>
  );
}
function Dot({ ok, label }: { ok: boolean; label: string }) {
  return <span className={`inline-flex items-center gap-1 ${ok ? "text-match-fg" : "text-ink-400"}`}><span className={`h-2 w-2 rounded-full ${ok ? "bg-match" : "bg-ink-200"}`} aria-hidden />{label}</span>;
}
