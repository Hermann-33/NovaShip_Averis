"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, getSession, register } from "@/lib/api";
import { AuthError, AuthLayout, Field, PasswordInput, ROLE_LABELS, SubmitButton, inputClass } from "@/components/auth";

type AuthConfig = { register_roles: string[]; min_password_length: number };

export default function RegisterPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [role, setRole] = useState("");
  const [cfg, setCfg] = useState<AuthConfig>({ register_roles: ["OPERATIONS_STAFF"], min_password_length: 8 });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (getSession()) { router.replace("/"); return; }
    api<AuthConfig>("/auth/config", {}, { auth: false }).then((c) => { setCfg(c); setRole(c.register_roles[0] || ""); }).catch(() => {});
  }, [router]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setErr(null);
    if (password !== confirm) return setErr("Passwords do not match.");
    if (password.length < cfg.min_password_length) return setErr(`Password must be at least ${cfg.min_password_length} characters.`);
    setBusy(true);
    try { await register({ email: email.trim(), password, display_name: name.trim(), role: role || undefined }); router.replace("/welcome"); }
    catch (x: any) { setErr(x.message || "Could not create the account."); }
    finally { setBusy(false); }
  };

  return (
    <AuthLayout title="Create an account" subtitle="Self-registered accounts start with least privilege. An Admin can widen the role later."
      footer={<span>Already have an account? <Link href="/login" className="font-semibold text-accent-fg hover:underline">Sign in</Link></span>}>
      <form onSubmit={submit} className="space-y-4">
        <AuthError msg={err} />
        <Field label="Full name">
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Hari Mardianto" autoComplete="name" required minLength={2} autoFocus className={inputClass} />
        </Field>
        <Field label="Work email">
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@aprilasia.com" autoComplete="email" required className={inputClass} />
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Password" hint={`At least ${cfg.min_password_length} characters.`}>
            <PasswordInput value={password} onChange={setPassword} autoComplete="new-password" minLength={cfg.min_password_length} />
          </Field>
          <Field label="Confirm password">
            <PasswordInput value={confirm} onChange={setConfirm} autoComplete="new-password" minLength={cfg.min_password_length} />
          </Field>
        </div>
        <Field label="Role" hint={cfg.register_roles.length > 1 ? "Approving external sends and editing policy stay with Supervisors and Admins." : "Operations staff can view, compare, edit drafts, share internally and assign. Supervisor, Admin and Auditor roles are granted by an Admin."}>
          {cfg.register_roles.length > 1 ? (
            <select value={role} onChange={(e) => setRole(e.target.value)} className={inputClass}>
              {cfg.register_roles.map((r) => <option key={r} value={r}>{ROLE_LABELS[r] || r}</option>)}
            </select>
          ) : (
            <div className="inline-flex items-center gap-2 rounded-xl border border-ink-200 bg-ink-50 px-3 py-2 text-sm text-ink-800">
              <span className="h-2 w-2 rounded-full bg-accent" aria-hidden />{ROLE_LABELS[cfg.register_roles[0]] || cfg.register_roles[0] || "Operations staff"}
            </div>
          )}
        </Field>
        <SubmitButton busy={busy}>Create account</SubmitButton>
      </form>
    </AuthLayout>
  );
}
