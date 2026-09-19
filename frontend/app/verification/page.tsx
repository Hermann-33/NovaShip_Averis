"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api, FIELD_LABELS, SEVEN_FIELDS } from "@/lib/api";
import { Badge, Button, Card, Confidence, Empty, RESULT_STYLES, StatusBadge, Toast } from "@/components/ui";

type FieldStat = { field: string; label: string; match: number; mismatch: number; review: number; examples: { case_id: string; si: string; bl: string }[] };

/** Seven-field verification overview: where each of the seven fields is compared, how often it fails, and every case per field. */
export default function VerificationPage() {
  const [stats, setStats] = useState<{ compared_cases: number; fields: FieldStat[] } | null>(null);
  const [field, setField] = useState<string>("container_count");
  const [result, setResult] = useState<string>("MISMATCH");
  const [rows, setRows] = useState<any[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => { api("/dashboard/fields").then(setStats).catch((e) => setErr(e.message)); }, []);
  useEffect(() => { setRows(null); api(`/dashboard/field/${field}${result ? `?result=${result}` : ""}`).then((d) => setRows(d.items)).catch((e) => setErr(e.message)); }, [field, result]);

  if (err) return <Toast msg={err} kind="err" />;
  const total = stats?.compared_cases || 0;
  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-ink-900">Seven-field verification</h1>
          <p className="max-w-[70ch] text-sm text-ink-600">The Shipping Instruction is the source of truth. Every compared case checks exactly these seven fields, each independently. Click a field to see every case where it was compared.</p>
        </div>
        <div className="text-right text-xs text-ink-500">{total} cases compared<br /><Link href="/" className="text-accent hover:underline">back to inbox</Link></div>
      </header>

      <div className="grid grid-cols-2 gap-2 md:grid-cols-4 xl:grid-cols-7">
        {(stats?.fields || SEVEN_FIELDS.map((f) => ({ field: f, label: FIELD_LABELS[f], match: 0, mismatch: 0, review: 0, examples: [] }))).map((s, i) => {
          const sel = s.field === field;
          const pct = total ? Math.round((s.mismatch / total) * 100) : 0;
          return (
            <button key={s.field} onClick={() => setField(s.field)} aria-pressed={sel} className={`rounded-xl border p-3 text-left transition active:scale-[0.98] ${sel ? "border-accent bg-accent-bg/40 ring-1 ring-accent" : "border-ink-200 bg-white hover:bg-ink-50"}`}>
              <div className="text-[11px] text-ink-500">Field {i + 1} of 7</div>
              <div className="text-sm font-semibold text-ink-900">{s.label}</div>
              <div className="mt-2 flex items-baseline gap-1"><span className="text-2xl font-semibold tabular-nums text-mismatch">{s.mismatch}</span><span className="text-xs text-ink-500">mismatch, {pct}%</span></div>
              <div className="mt-1 flex h-1.5 w-full overflow-hidden rounded bg-ink-100" aria-hidden>
                <span className="bg-match" style={{ width: `${total ? (s.match / total) * 100 : 0}%` }} /><span className="bg-mismatch" style={{ width: `${total ? (s.mismatch / total) * 100 : 0}%` }} /><span className="bg-review" style={{ width: `${total ? (s.review / total) * 100 : 0}%` }} />
              </div>
              <div className="mt-1 text-[11px] text-ink-500">{s.match} match, {s.review} review</div>
            </button>
          );
        })}
      </div>

      <Card title={<span>{FIELD_LABELS[field]}: cases</span>} right={
        <div className="flex gap-1">
          {["MISMATCH", "MATCH", "MISSING_IN_SI", "MISSING_IN_BL", "LOW_CONFIDENCE_REVIEW", ""].map((r) => <Button key={r || "all"} kind={result === r ? "primary" : "ghost"} onClick={() => setResult(r)}>{r ? RESULT_STYLES[r]?.label || r : "All"}</Button>)}
        </div>}>
        {rows === null ? <SkeletonRows /> : rows.length === 0 ? <Empty text={`No cases with ${FIELD_LABELS[field]} = ${result || "any result"}.`} /> : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] text-xs">
              <thead className="text-[11px] uppercase tracking-wide text-ink-500"><tr><th className="px-2 py-1.5 text-left">Case</th><th className="px-2 text-left">Subject</th><th className="px-2 text-left">SI value (truth)</th><th className="px-2 text-left">Draft BL value</th><th className="px-2 text-left">Labels resolved</th><th className="px-2 text-left">Result</th><th className="px-2 text-left">Confidence</th><th className="px-2 text-left">Status</th></tr></thead>
              <tbody>{rows.map((r) => (
                <tr key={r.case_id} className={`border-t border-ink-100 ${RESULT_STYLES[r.result]?.row || ""}`}>
                  <td className="px-2 py-1.5 font-mono"><Link href={`/cases/${r.case_id}?tab=compare`} className="text-accent hover:underline">{r.case_id.replace("case_", "")}</Link></td>
                  <td className="max-w-[320px] truncate px-2 py-1.5" title={r.subject}>{r.subject}</td>
                  <td className="px-2 py-1.5 font-mono">{r.si ?? <span className="italic text-review-fg">blank</span>}</td>
                  <td className="px-2 py-1.5 font-mono">{r.bl ?? <span className="italic text-review-fg">blank</span>}</td>
                  <td className="px-2 py-1.5 text-ink-500">{r.si_label || "-"} / {r.bl_label || "-"}</td>
                  <td className="px-2 py-1.5"><Badge className={`border ${RESULT_STYLES[r.result]?.badge}`}>{RESULT_STYLES[r.result]?.label || r.result}</Badge></td>
                  <td className="px-2 py-1.5"><Confidence value={r.confidence} /></td>
                  <td className="px-2 py-1.5"><StatusBadge status={r.status} /></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title="Where the seven fields are implemented">
        <div className="grid gap-3 text-xs md:grid-cols-2">
          <ol className="list-decimal space-y-1 pl-5">
            <li><code>backend/app/contracts/schemas.py</code>: <code>SEVEN_FIELDS</code> and <code>FIELD_LABELS</code> (the frozen list).</li>
            <li><code>backend/app/ai/extractor.py</code>: <code>LABEL_SYNONYMS</code> resolves labels such as Load Port, To the Order of, Gross Wt (kgs).</li>
            <li><code>backend/app/core/normalizer.py</code>: safe normalisation per field (kg, integer count, port code stripping).</li>
            <li><code>backend/app/core/comparator.py</code>: <code>compare_seven_fields()</code>, the deterministic verdict.</li>
            <li><code>supabase/migrations/0001_schema.sql</code>: <code>comparison_fields.field_name</code> CHECK constraint, exactly these seven names.</li>
            <li><code>frontend/components/comparison.tsx</code>: the seven-field card shown on every case.</li>
          </ol>
          <div className="rounded-lg bg-ink-50 p-3">
            <div className="mb-1 font-semibold text-ink-800">All seven match</div>
            <div className="font-mono text-match-fg">No mismatch detected.</div>
            <div className="mt-2 font-semibold text-ink-800">One field differs</div>
            <pre className="font-mono text-[11px] text-ink-800">1 mismatch detected{"\n"}Container Count: SI 3 x 40&apos;HC, BL 4 x 40&apos;HC{"\n"}Gross Weight (kg): MATCH</pre>
          </div>
        </div>
      </Card>
    </div>
  );
}

function SkeletonRows() {
  return <div className="space-y-2" aria-busy>{[0, 1, 2, 3, 4].map((i) => <div key={i} className="h-7 animate-pulse rounded bg-ink-100" />)}</div>;
}
