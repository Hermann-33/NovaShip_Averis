import Link from "next/link";

/**
 * Guide page for first-time users and demo judges.
 * Design read: trust-first B2B guide page for shipping operators. Variance 5, motion 3, density 4.
 * Single accent (orange), 12px radius, no decorative eyebrows, split hero, four different section layouts.
 */
export const metadata = { title: "Guide, NovaShip Averis" };

const STEPS = [
  { title: "Open the Inbox", body: "Every email is already a case. Filter Mismatch = yes to see what needs a decision today.", href: "/", cta: "Open inbox" },
  { title: "Read the seven fields", body: "On a case, the comparison card shows Shipper, Consignee, Notify Party, Port of Loading, Port of Discharge, Container Count and Gross Weight side by side with the Shipping Instruction as truth.", href: "/cases/case_email_004", cta: "See a mismatch case" },
  { title: "Check the evidence", body: "Each value links to the exact line in the document and shows which label was resolved, for example Load Port to Port of Loading.", href: "/cases/case_email_004?tab=evidence", cta: "View evidence" },
  { title: "Approve, edit or reject the draft", body: "The correction request is written for you but never sent. A Supervisor approves; Operations staff can edit and share internally.", href: "/cases/case_email_004?tab=drafts", cta: "Open drafts" },
  { title: "Notify the right party", body: "Pick an approved recipient, preview exactly the fields that will be disclosed, confirm. The extracted Notify Party is a value to compare, not permission to send.", href: "/cases/case_email_004?tab=collab", cta: "Try Notify Party" },
  { title: "Ask the assistant", body: "Questions are answered only from this case, the documents, the comparison and the policy knowledge base, with citations.", href: "/cases/case_email_004?tab=ask", cta: "Ask AI" },
];

const ROLES = [
  ["Operations staff", "Najiha, Deswita, Willy, Mitchelle", "view, compare, edit drafts, share internally, assign"],
  ["Supervisor", "Hari, Teo Ei Leen", "everything above plus approve external sends and notify external parties"],
  ["Admin", "Syed Faraz Ali", "everything plus edit policy and rebuild the knowledge index"],
  ["Auditor", "Ooi Sok Yong", "read-only, including the global audit log"],
];

export default function WelcomePage() {
  return (
    <div className="space-y-12 pb-8">
      <section className="grid items-center gap-8 pt-6 md:grid-cols-[1.1fr_1fr]">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight text-ink-900 md:text-4xl">Every email becomes a case. Every verdict shows its evidence.</h1>
          <p className="mt-3 max-w-[60ch] text-base leading-relaxed text-ink-600">NovaShip Averis reads the shared shipping inbox, checks each Draft Bill of Lading against its Shipping Instruction on seven fields, and asks a person before anything leaves the mailbox.</p>
          <div className="mt-5 flex flex-wrap gap-2">
            <Link href="/" className="rounded-xl bg-accent px-4 py-2 text-sm font-medium text-white transition hover:bg-accent-hover active:scale-[0.98]">Open the inbox</Link>
            <Link href="/agent" className="rounded-xl border border-ink-200 bg-white px-4 py-2 text-sm font-medium text-ink-800 transition hover:bg-ink-50 active:scale-[0.98]">See how the agent works</Link>
          </div>
        </div>
        <div className="rounded-xl border border-ink-200 bg-white p-5 shadow-sm">
          <div className="text-sm font-semibold text-ink-800">What a finished check looks like</div>
          <div className="mt-3 space-y-2 text-sm">
            {[["Shipper", "match"], ["Consignee", "match"], ["Notify Party", "match"], ["Port of Loading", "match"], ["Port of Discharge", "match"], ["Container Count", "mismatch"], ["Gross Weight (kg)", "match"]].map(([f, r]) => (
              <div key={f} className={`flex items-center justify-between rounded-lg px-3 py-1.5 ${r === "mismatch" ? "bg-mismatch-bg text-mismatch-fg" : "bg-ink-50 text-ink-700"}`}>
                <span>{f}</span><span className="font-mono text-xs">{r === "mismatch" ? "SI 3 x 40'HC, BL 4 x 40'HC" : "match"}</span>
              </div>
            ))}
          </div>
          <p className="mt-3 text-xs text-ink-500">One field differs, so only one field is flagged. When all seven match the result reads: No mismatch detected.</p>
        </div>
      </section>

      <section>
        <h2 className="text-xl font-semibold text-ink-900">Six steps for an operator</h2>
        <ol className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {STEPS.map((s, i) => (
            <li key={s.title} className="flex flex-col rounded-xl border border-ink-200 bg-white p-4">
              <div className="text-xs text-ink-500">Step {i + 1}</div>
              <div className="mt-1 font-semibold text-ink-900">{s.title}</div>
              <p className="mt-1 flex-1 text-sm leading-relaxed text-ink-600">{s.body}</p>
              <Link href={s.href} className="mt-3 text-sm font-medium text-accent hover:underline">{s.cta}</Link>
            </li>
          ))}
        </ol>
      </section>

      <section className="rounded-xl bg-gradient-to-br from-accent to-[#f97316] p-6 text-white shadow-glow">
        <h2 className="text-xl font-semibold">How the AI is kept honest</h2>
        <div className="mt-4 grid gap-6 md:grid-cols-3">
          <div><div className="font-semibold">AI reads and drafts</div><p className="mt-1 text-sm text-orange-50">Security agent, intent, document type, field extraction, summary, reply draft, translation and the case assistant.</p></div>
          <div><div className="font-semibold">Code decides</div><p className="mt-1 text-sm text-orange-50">The seven-field comparison is a deterministic function with unit tests. A model can call it as a tool but can never overrule it.</p></div>
          <div><div className="font-semibold">People approve</div><p className="mt-1 text-sm text-orange-50">The LangGraph pauses at human review. External email and Notify Party messages need a Supervisor. Everything is written to an append-only audit log.</p></div>
        </div>
      </section>

      <section>
        <h2 className="text-xl font-semibold text-ink-900">Who can do what</h2>
        <p className="mt-1 max-w-[65ch] text-sm text-ink-600">Switch the acting user in the header to try each role. Permissions are enforced by the API, not just hidden in the UI.</p>
        <div className="mt-4 overflow-x-auto rounded-xl border border-ink-200 bg-white">
          <table className="w-full min-w-[640px] text-sm">
            <thead className="bg-ink-50 text-left text-xs uppercase tracking-wide text-ink-500"><tr><th className="px-4 py-2">Role</th><th className="px-4 py-2">Demo users</th><th className="px-4 py-2">Can</th></tr></thead>
            <tbody>{ROLES.map(([r, u, c]) => <tr key={r} className="border-t border-ink-100"><td className="px-4 py-2 font-medium text-ink-900">{r}</td><td className="px-4 py-2 text-ink-600">{u}</td><td className="px-4 py-2 text-ink-600">{c}</td></tr>)}</tbody>
          </table>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-ink-200 bg-white p-5">
          <h2 className="text-lg font-semibold text-ink-900">Pages</h2>
          <ul className="mt-2 space-y-1.5 text-sm text-ink-700">
            <li><Link className="text-accent hover:underline" href="/">Inbox</Link>: metrics, case table, filters, batch actions.</li>
            <li><Link className="text-accent hover:underline" href="/verification">Seven fields</Link>: per-field mismatch statistics and every case per field.</li>
            <li><Link className="text-accent hover:underline" href="/security">Security</Link>: what the security agent flagged and why.</li>
            <li><Link className="text-accent hover:underline" href="/agent">AI agent</Link>: run the LangGraph on a case, see the pause, resume with a decision.</li>
            <li><Link className="text-accent hover:underline" href="/audit">Audit</Link>: global append-only history.</li>
            <li><Link className="text-accent hover:underline" href="/policies">Policies</Link>: versioned thresholds and rules (Admin edits).</li>
          </ul>
        </div>
        <div className="rounded-xl border border-ink-200 bg-white p-5">
          <h2 className="text-lg font-semibold text-ink-900">Try these cases</h2>
          <ul className="mt-2 space-y-1.5 text-sm text-ink-700">
            <li><Link className="font-mono text-accent hover:underline" href="/cases/case_email_004">case_email_004</Link>: Consignee and Notify Party differ.</li>
            <li><Link className="font-mono text-accent hover:underline" href="/cases/case_email_001">case_email_001</Link>: all seven match.</li>
            <li><Link className="font-mono text-accent hover:underline" href="/cases/case_email_499">case_email_499</Link>: only Gross Weight differs.</li>
            <li><Link className="font-mono text-accent hover:underline" href="/cases/case_email_507">case_email_507</Link>: Draft BL missing, upload it to continue.</li>
            <li><Link className="font-mono text-accent hover:underline" href="/cases/case_email_512">case_email_512</Link>: scanned PDF, human review with reason.</li>
            <li><Link className="font-mono text-accent hover:underline" href="/cases/case_email_015">case_email_015</Link>: spam, no reply needed.</li>
          </ul>
        </div>
      </section>
    </div>
  );
}
