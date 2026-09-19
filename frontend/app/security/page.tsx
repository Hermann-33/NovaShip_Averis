"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import { Badge, Button, Card, Empty, StatusBadge, Toast } from "@/components/ui";

const TONE: Record<string, string> = { SECURITY_REVIEW: "bg-mismatch text-white", SPAM: "bg-mismatch-bg text-mismatch-fg", SUSPICIOUS: "bg-review-bg text-review-fg", SAFE: "bg-match-bg text-match-fg" };

/** Security agent queue: everything the precheck + security agent flagged, with evidence and one-click actions. */
export default function SecurityPage() {
  const [rows, setRows] = useState<any[] | null>(null);
  const [filter, setFilter] = useState("");
  const [toast, setToast] = useState<{ msg: string; kind: "ok" | "err" } | null>(null);
  const say = (msg: string, kind: "ok" | "err" = "ok") => { setToast({ msg, kind }); setTimeout(() => setToast(null), 3500); };
  const load = () => api("/security/queue").then((d) => setRows(d.items)).catch((e) => say(e.message, "err"));
  useEffect(() => { load(); }, []);
  const act = async (id: string, path: string) => { try { await post(`/cases/${id}${path}`); say("Done"); load(); } catch (e: any) { say(e.message, "err"); } };
  const shown = (rows || []).filter((r) => !filter || r.outcome === filter);
  const counts: Record<string, number> = (rows || []).reduce((m: Record<string, number>, r) => ({ ...m, [r.outcome]: (m[r.outcome] || 0) + 1 }), {} as Record<string, number>);

  return (
    <div className="space-y-4">
      {toast && <Toast {...toast} />}
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-ink-900">Security agent</h1>
          <p className="max-w-[70ch] text-sm text-ink-600">Deterministic precheck (phrases, sender domain, links, blocked attachment types, duplicates, policy-bypass requests) plus an LLM security agent that may only escalate, never downgrade. Attachments are parsed to text and never executed.</p>
        </div>
        <div className="flex gap-1">
          {["", "SECURITY_REVIEW", "SUSPICIOUS", "SPAM"].map((k) => <Button key={k || "all"} kind={filter === k ? "primary" : "ghost"} onClick={() => setFilter(k)}>{k ? `${k.replace("_", " ")} (${counts[k] || 0})` : `All (${rows?.length || 0})`}</Button>)}
        </div>
      </header>
      {rows === null ? <div className="space-y-2" aria-busy>{[0, 1, 2].map((i) => <div key={i} className="h-24 animate-pulse rounded-xl bg-ink-100" />)}</div>
        : shown.length === 0 ? <Empty text="Nothing flagged. The inbox is clean for this filter." />
        : shown.map((r) => (
          <Card key={r.case_id} title={<span className="flex items-center gap-2"><Badge className={TONE[r.outcome]}>{r.outcome.replace("_", " ")}</Badge><Link href={`/cases/${r.case_id}`} className="font-mono text-xs text-accent hover:underline">{r.case_id}</Link><span className="truncate text-sm font-medium">{r.subject}</span></span>}
            right={<span className="flex items-center gap-2 text-xs"><StatusBadge status={r.status} /><span className="text-ink-500">score {r.score}</span></span>}>
            <div className="mb-2 text-xs text-ink-500">from <span className="font-mono">{r.sender}</span></div>
            <ul className="grid gap-1 text-xs md:grid-cols-2">
              {r.signals.map((s: any, i: number) => <li key={i} className="rounded-md bg-ink-50 p-2"><b>{s.signal}</b> <span className="text-ink-500">({s.severity})</span><div className="text-ink-700">{s.evidence}</div><div className="text-ink-500">Recommended: {s.recommended_action}</div></li>)}
              {r.anomalies.map((s: any, i: number) => <li key={`a${i}`} className="rounded-md bg-review-bg/50 p-2"><b>{s.signal}</b> <span className="text-ink-500">({s.severity})</span><div className="text-ink-700">{s.evidence}</div><div className="text-ink-500">Recommended: {s.recommended_action}</div></li>)}
            </ul>
            <div className="mt-2 flex flex-wrap gap-1">
              <Link href={`/cases/${r.case_id}`}><Button kind="primary">Open case</Button></Link>
              <Button onClick={() => act(r.case_id, "/request-review")}>Send to human review</Button>
              <Button onClick={() => act(r.case_id, "/no-action")}>Mark no action</Button>
              <Button onClick={() => act(r.case_id, "/complete")}>Archive</Button>
            </div>
          </Card>
        ))}
    </div>
  );
}
