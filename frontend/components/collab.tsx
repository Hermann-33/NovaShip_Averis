"use client";
import { useEffect, useState } from "react";
import { api, post, type CaseView } from "@/lib/api";
import { Badge, Button, Card, Empty, fmtDate } from "@/components/ui";

type Recipient = { id: string; label: string; recipient_type: string; external: boolean; roles: string[]; allowed: boolean };

/** Notify Party + selected-user sharing: Select Recipient -> Preview -> Confirm -> Send/Share -> Audit -> Status. */
export function CollaborationPanel({ c, onChange, say }: { c: CaseView; onChange: () => void; say: (m: string, k?: "ok" | "err") => void }) {
  const [recips, setRecips] = useState<Recipient[]>([]);
  const [np, setNp] = useState<any>(null);
  const [pick, setPick] = useState<string>("");
  const [message, setMessage] = useState("");
  const [due, setDue] = useState("");
  const [fields, setFields] = useState<string[]>(c.comparison?.mismatch_fields || []);
  const [preview, setPreview] = useState<any>(null);
  const [users, setUsers] = useState<any[]>([]);
  const [shares, setShares] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [assignTo, setAssignTo] = useState("");

  const reload = () => {
    api(`/cases/${c.id}/recipients`).then((d) => setRecips(d.recipients)).catch(() => {});
    api(`/cases/${c.id}/audit`).then((d) => setShares(d.shares)).catch(() => {});
    api("/users").then((d) => setUsers(d.users)).catch(() => {});
  };
  useEffect(reload, [c.id, c.updated_at]);

  const chosen = recips.find((r) => r.id === pick);
  const beginNotify = async () => { setBusy(true); try { const d = await post(`/cases/${c.id}/notify-party`); setNp(d); setRecips(d.recipients); say("Notify Party flow started — select an authorised recipient"); onChange(); } catch (e: any) { say(e.message, "err"); } finally { setBusy(false); } };
  const body = (preview_only: boolean, confirm_external = false) => ({
    recipient_type: chosen!.recipient_type, recipient_user_id: chosen!.external ? undefined : chosen!.id, recipient_party_id: chosen!.external ? chosen!.id : undefined,
    message: message || undefined, due_date: due || undefined, include_fields: fields, preview_only, confirm_external,
  });
  const doPreview = async () => { if (!chosen) return say("Select a recipient", "err"); setBusy(true); try { setPreview(await post(`/cases/${c.id}/share`, body(true))); } catch (e: any) { say(e.message, "err"); } finally { setBusy(false); } };
  const doSend = async () => {
    if (!chosen) return; setBusy(true);
    try {
      const r = chosen.external && preview?.share?.id ? await post(`/cases/${c.id}/share/${preview.share.id}/confirm`) : await post(`/cases/${c.id}/share`, body(false, true));
      say(r.share.is_external ? "External notification sent & audited" : "Shared internally & audited"); setPreview(null); setPick(""); onChange(); reload();
    } catch (e: any) { say(e.message, "err"); } finally { setBusy(false); }
  };
  const assign = async () => { if (!assignTo) return; try { await post(`/cases/${c.id}/assign`, { user_id: assignTo }); say("Assigned"); onChange(); } catch (e: any) { say(e.message, "err"); } };
  const ack = async (id: string) => { try { await post(`/shares/${id}/acknowledge`, { response: "Acknowledged" }); reload(); } catch (e: any) { say(e.message, "err"); } };

  const npField = c.comparison?.fields.find((f) => f.field === "notify_party");
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="space-y-4">
        <Card title="Assign owner">
          <div className="flex gap-2">
            <select value={assignTo} onChange={(e) => setAssignTo(e.target.value)} className="flex-1 rounded-md border border-ink-200 px-2 py-1.5 text-sm">
              <option value="">Select internal user…</option>
              {users.map((u) => <option key={u.id} value={u.id}>{u.display_name} · {u.roles.join("/")}</option>)}
            </select>
            <Button kind="primary" onClick={assign}>Assign / Reassign</Button>
          </div>
          <div className="mt-2 text-xs text-ink-500">Currently: {users.find((u) => u.id === c.assigned_user_id)?.display_name || "unassigned"}{c.assigned_team_id ? ` · team ${c.assigned_team_id}` : ""}</div>
        </Card>

        <Card title="Notify Party" right={<Button kind="primary" disabled={busy} onClick={beginNotify}>Start Notify Party flow</Button>}>
          {npField ? (
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div className="rounded-md bg-ink-50 p-2"><div className="text-[11px] uppercase text-ink-500">Notify Party on SI</div><div className="font-mono text-xs">{npField.si_original || "—"}</div></div>
              <div className="rounded-md bg-ink-50 p-2"><div className="text-[11px] uppercase text-ink-500">Notify Party on Draft BL</div><div className="font-mono text-xs">{npField.bl_original || "—"}</div></div>
              <div className="col-span-2"><Badge className={npField.result === "MATCH" ? "bg-match-bg text-match-fg" : "bg-mismatch-bg text-mismatch-fg"}>{npField.result === "MATCH" ? "values match" : npField.result.replace(/_/g, " ")}</Badge></div>
            </div>
          ) : <Empty text="Notify Party not extracted yet (no comparison)." />}
          <p className="mt-3 text-xs text-ink-500">The extracted Notify Party is a <b>comparison value</b>, not authorisation to send. Choose an approved recipient below, preview exactly what will be shared, then confirm.</p>
        </Card>

        <Card title="Select recipient">
          <div className="max-h-64 space-y-1 overflow-auto scrollbar-thin">
            {recips.map((r) => (
              <label key={r.id} className={`flex items-center gap-2 rounded-md border px-2 py-1.5 text-xs ${pick === r.id ? "border-accent bg-accent-bg/40" : "border-ink-100"} ${!r.allowed ? "opacity-50" : ""}`}>
                <input type="radio" name="recip" disabled={!r.allowed} checked={pick === r.id} onChange={() => setPick(r.id)} />
                <span className="flex-1 truncate">{r.label}</span>
                <Badge className={r.external ? "bg-accent-soft text-accent-fg" : "bg-ink-100 text-ink-700"}>{r.external ? "External" : "Internal"}</Badge>
                <span className="text-[10px] text-ink-500">{r.roles.join("/")}</span>
                {!r.allowed && <span className="text-[10px] text-mismatch">not permitted</span>}
              </label>
            ))}
          </div>
          <div className="mt-3 grid gap-2">
            <div className="text-[11px] uppercase text-ink-500">Fields to include (default: mismatches only)</div>
            <div className="flex flex-wrap gap-2 text-xs">
              {(c.comparison?.fields || []).map((f) => (
                <label key={f.field} className="flex items-center gap-1"><input type="checkbox" checked={fields.includes(f.field)} onChange={(e) => setFields(e.target.checked ? [...fields, f.field] : fields.filter((x) => x !== f.field))} />{f.label}{f.result === "MISMATCH" && <span className="text-mismatch">●</span>}</label>
              ))}
            </div>
            <textarea value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Optional message to the recipient" className="rounded-md border border-ink-200 p-2 text-sm" rows={2} />
            <div className="flex items-center gap-2 text-xs"><span className="text-ink-500">Due date</span><input type="date" value={due} onChange={(e) => setDue(e.target.value)} className="rounded-md border border-ink-200 px-2 py-1" /></div>
            <div className="flex gap-2"><Button disabled={!chosen || busy} onClick={doPreview}>Preview</Button>{chosen && !chosen.external && <Button kind="primary" disabled={busy} onClick={doSend}>Share internally</Button>}</div>
          </div>
        </Card>
      </div>

      <div className="space-y-4">
        <Card title="Preview — exactly what will be shared">
          {preview ? (
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-xs"><Badge className={preview.share.is_external ? "bg-accent-soft text-accent-fg" : "bg-ink-100 text-ink-700"}>{preview.share.is_external ? "External" : "Internal"}</Badge><span className="text-ink-500">to {preview.share.recipient_label}</span></div>
              <pre className="whitespace-pre-wrap rounded-md bg-ink-50 p-3 font-mono text-[11px] text-ink-900">{preview.preview}</pre>
              {preview.requires_confirmation ? (
                <div className="rounded-md border border-review bg-review-bg p-3 text-xs text-review-fg">
                  <b>Human confirmation required for external sending.</b> Only the fields listed above are disclosed. The original email body is not included.
                  <div className="mt-2"><Button kind="success" disabled={busy} onClick={doSend}>Confirm & send to external party</Button></div>
                </div>
              ) : <Button kind="primary" disabled={busy} onClick={doSend}>Send / share</Button>}
            </div>
          ) : <Empty text="Select a recipient and click Preview." />}
        </Card>

        <Card title="Shares & notifications">
          {shares.length ? (
            <table className="w-full text-xs">
              <thead className="text-[11px] uppercase text-ink-500"><tr><th className="py-1 text-left">Recipient</th><th className="text-left">Type</th><th className="text-left">Status</th><th className="text-left">Sent</th><th className="text-left">Viewed / Ack</th><th /></tr></thead>
              <tbody>{shares.map((s) => (
                <tr key={s.id} className="border-t border-ink-100">
                  <td className="py-1.5 pr-2">{s.recipient_label}<div className="text-[10px] text-ink-500">by {s.shared_by}</div></td>
                  <td><Badge className={s.is_external ? "bg-accent-soft text-accent-fg" : "bg-ink-100 text-ink-700"}>{s.recipient_type.replace(/_/g, " ")}</Badge></td>
                  <td>{s.status}</td><td className="whitespace-nowrap">{fmtDate(s.sent_at)}</td><td className="whitespace-nowrap">{s.acknowledged_at ? `ack ${fmtDate(s.acknowledged_at)}` : s.viewed_at ? fmtDate(s.viewed_at) : "—"}</td>
                  <td>{s.status === "SENT" && <Button kind="ghost" onClick={() => ack(s.id)}>Mark acknowledged</Button>}</td>
                </tr>
              ))}</tbody>
            </table>
          ) : <Empty text="Nothing shared yet." />}
        </Card>
      </div>
    </div>
  );
}
