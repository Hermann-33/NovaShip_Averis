"use client";
import { useEffect, useState } from "react";
import { api, put } from "@/lib/api";
import { Badge, Button, Card, Empty, Toast, fmtDate } from "@/components/ui";

export default function PoliciesPage() {
  const [data, setData] = useState<any>(null);
  const [draft, setDraft] = useState("");
  const [note, setNote] = useState("");
  const [toast, setToast] = useState<{ msg: string; kind: "ok" | "err" } | null>(null);
  const [perms, setPerms] = useState<string[]>([]);
  const say = (msg: string, kind: "ok" | "err" = "ok") => { setToast({ msg, kind }); setTimeout(() => setToast(null), 3500); };
  const load = () => api("/policies").then((d) => { setData(d); setDraft(JSON.stringify(d.effective, null, 2)); }).catch((e) => say(e.message, "err"));
  useEffect(() => { load(); api("/me").then((m) => setPerms(m.permissions)).catch(() => {}); }, []);
  const save = async () => {
    try { const body = JSON.parse(draft); await put("/policies", { ...body, change_note: note || "policy update" }); say("Policy saved as new version (audited)"); setNote(""); load(); }
    catch (e: any) { say(e.message, "err"); }
  };
  if (!data) return <div className="p-8 text-center text-sm text-ink-500">Loading…</div>;
  const canEdit = perms.includes("edit_policy");
  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
      {toast && <Toast {...toast} />}
      <div className="space-y-4">
        <Card title={<span>Active policy <Badge className="bg-accent-bg text-accent-fg">{data.active.version}</Badge></span>} right={<span className="text-xs text-ink-500">by {data.active.updated_by} · {fmtDate(data.active.updated_at)}</span>}>
          <ul className="list-disc space-y-1 pl-5 text-sm">{data.explanation.map((l: string, i: number) => <li key={i}>{l}</li>)}</ul>
        </Card>
        <Card title="Version history (every change is audited)">
          {data.versions.length ? <table className="w-full text-xs"><thead className="text-[11px] uppercase text-ink-500"><tr><th className="text-left py-1">Version</th><th className="text-left">By</th><th className="text-left">When</th><th className="text-left">Note</th></tr></thead>
            <tbody>{[...data.versions].reverse().map((v: any) => <tr key={v.id} className="border-t border-ink-100"><td className="py-1 font-mono">{v.version}</td><td>{v.updated_by}</td><td>{fmtDate(v.updated_at)}</td><td>{v.change_note}</td></tr>)}</tbody></table> : <Empty text="No versions" />}
        </Card>
      </div>
      <Card title="Edit policy (ADMIN)" right={canEdit ? <Button kind="primary" onClick={save}>Save as new version</Button> : <span className="text-xs text-mismatch">read-only — requires ADMIN role</span>}>
        <p className="mb-2 text-xs text-ink-500">Sections: verification (source of truth, seven fields, weight unit, confidence threshold, legal-name & port alias policy) · human_review · communication · security · intent. The seven-field baseline is fixed; you can tune thresholds and lists.</p>
        <textarea value={draft} onChange={(e) => setDraft(e.target.value)} rows={28} disabled={!canEdit} className="w-full rounded-md border border-ink-200 p-2 font-mono text-[11px]" />
        <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Change note (required for audit)" disabled={!canEdit} className="mt-2 w-full rounded-md border border-ink-200 px-2 py-1.5 text-sm" />
      </Card>
    </div>
  );
}
