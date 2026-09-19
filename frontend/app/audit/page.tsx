"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Badge, Button, Empty, fmtDate } from "@/components/ui";

/** Global append-only audit log (Supervisor, Admin, Auditor). */
export default function AuditPage() {
  const [events, setEvents] = useState<any[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [action, setAction] = useState("");
  const [actor, setActor] = useState("");
  const [limit, setLimit] = useState(200);
  useEffect(() => {
    setEvents(null);
    const qs = new URLSearchParams({ limit: String(limit) }); if (action) qs.set("action", action); if (actor) qs.set("actor_type", actor);
    api(`/audit?${qs}`).then((d) => { setEvents(d.events); setErr(null); }).catch((e) => setErr(e.message));
  }, [action, actor, limit]);

  return (
    <div className="space-y-3">
      <header>
        <h1 className="text-xl font-semibold text-ink-900">Audit history</h1>
        <p className="max-w-[70ch] text-sm text-ink-600">Every classification, field result, draft, approval, share and error across all cases. Append-only: the database trigger rejects updates and deletes.</p>
      </header>
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <input placeholder="Filter by action, e.g. MISMATCH, SHARE, POLICY" value={action} onChange={(e) => setAction(e.target.value.toUpperCase())} className="w-72 rounded-md border border-ink-200 px-2 py-1.5" />
        {["", "USER", "AI", "SYSTEM"].map((a) => <Button key={a || "all"} kind={actor === a ? "primary" : "ghost"} onClick={() => setActor(a)}>{a || "All actors"}</Button>)}
        <select value={limit} onChange={(e) => setLimit(Number(e.target.value))} className="rounded-md border border-ink-200 px-2 py-1.5">{[100, 200, 500, 1000].map((n) => <option key={n} value={n}>last {n}</option>)}</select>
      </div>
      {err ? <div className="rounded-xl border border-mismatch bg-mismatch-bg p-4 text-sm text-mismatch-fg">{err}. Global audit requires the Supervisor, Admin or Auditor role. Switch user in the header.</div>
        : events === null ? <div className="space-y-2" aria-busy>{[0, 1, 2, 3, 4, 5].map((i) => <div key={i} className="h-8 animate-pulse rounded bg-ink-100" />)}</div>
        : events.length === 0 ? <Empty text="No events match." />
        : (
          <div className="overflow-auto rounded-xl border border-ink-200 bg-white">
            <table className="w-full min-w-[1000px] text-xs">
              <thead className="bg-ink-50 text-[11px] uppercase text-ink-500"><tr><th className="px-2 py-1.5 text-left">Time</th><th className="px-2 text-left">Case</th><th className="px-2 text-left">Actor</th><th className="px-2 text-left">Action</th><th className="px-2 text-left">After</th><th className="px-2 text-left">Policy</th></tr></thead>
              <tbody>{events.map((e) => (
                <tr key={e.event_id} className="border-t border-ink-100 align-top">
                  <td className="whitespace-nowrap px-2 py-1.5 font-mono text-[10px] text-ink-500">{fmtDate(e.timestamp)}</td>
                  <td className="px-2 py-1.5 font-mono text-[10px]">{e.case_id ? <Link href={`/cases/${e.case_id}?tab=audit`} className="text-accent hover:underline">{e.case_id.replace("case_", "")}</Link> : "-"}</td>
                  <td className="px-2 py-1.5"><Badge className={{ USER: "bg-accent-bg text-accent-fg", AI: "bg-accent-soft text-accent-fg", SYSTEM: "bg-ink-100 text-ink-700" }[e.actor_type as string]}>{e.actor_type}</Badge> <span className="text-[10px] text-ink-500">{e.actor_id}</span></td>
                  <td className="px-2 py-1.5 font-medium">{e.action}</td>
                  <td className="max-w-[480px] px-2 py-1.5 font-mono text-[10px] text-ink-700">{e.after ? JSON.stringify(e.after).slice(0, 240) : ""}</td>
                  <td className="px-2 py-1.5 text-[10px] text-ink-500">{e.policy_version}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
    </div>
  );
}
