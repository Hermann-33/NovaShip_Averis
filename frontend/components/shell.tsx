"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api, currentUserId, setCurrentUserId } from "@/lib/api";

type Me = { id: string; display_name: string; roles: string[]; permissions: string[] };

const NAV = [
  { href: "/", label: "Inbox" },
  { href: "/verification", label: "Seven fields" },
  { href: "/security", label: "Security" },
  { href: "/agent", label: "AI agent" },
  { href: "/audit", label: "Audit" },
  { href: "/policies", label: "Policies" },
  { href: "/welcome", label: "Guide" },
];

export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const [me, setMe] = useState<Me | null>(null);
  const [users, setUsers] = useState<{ id: string; display_name: string; roles: string[] }[]>([]);
  const [health, setHealth] = useState<any>(null);
  const [uid, setUid] = useState("u_sup_1");
  const [open, setOpen] = useState(false);

  useEffect(() => { setUid(currentUserId()); }, []);
  useEffect(() => {
    api<Me>("/me").then(setMe).catch(() => setMe(null));
    api("/users").then((d) => setUsers(d.users)).catch(() => {});
    api("/health").then(setHealth).catch(() => setHealth(null));
  }, [uid]);

  const active = (href: string) => (href === "/" ? path === "/" || path.startsWith("/cases") : path.startsWith(href));
  return (
    <div className="flex min-h-screen flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-white focus:px-3 focus:py-2">Skip to content</a>
      <header className="sticky top-0 z-40 h-14 border-b border-ink-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex h-full max-w-[1600px] items-center gap-4 px-4">
          <Link href="/" className="flex shrink-0 items-center gap-2" aria-label="NovaShip Averis home">
            <span className="grid h-7 w-7 place-items-center rounded-md bg-accent text-sm font-black text-white shadow-glow">N</span>
            <span className="text-sm font-semibold tracking-tight text-ink-900">NovaShip <span className="text-accent">Averis</span></span>
          </Link>
          <nav className="hidden items-center gap-0.5 text-sm lg:flex" aria-label="Primary">
            {NAV.map((n) => (
              <Link key={n.href} href={n.href} aria-current={active(n.href) ? "page" : undefined} className={`whitespace-nowrap rounded-md px-2.5 py-1.5 ${active(n.href) ? "bg-accent-bg text-accent-fg" : "text-ink-600 hover:bg-ink-100 hover:text-ink-900"}`}>{n.label}</Link>
            ))}
          </nav>
          <button className="rounded-md border border-ink-200 px-2 py-1 text-xs text-ink-700 lg:hidden" onClick={() => setOpen(!open)} aria-expanded={open} aria-controls="mobile-nav">Menu</button>
          <div className="ml-auto flex items-center gap-3 text-xs">
            <span className={`hidden items-center gap-1.5 whitespace-nowrap xl:flex ${health ? "text-match" : "text-mismatch"}`} title={health ? `repository: ${health.backend}` : "backend unreachable"}>
              <span className={`h-2 w-2 rounded-full ${health ? "bg-match" : "bg-mismatch"}`} aria-hidden />{health ? `API online, ${health.cases} cases` : "API offline"}
            </span>
            <label className="flex items-center gap-2 text-ink-500">
              <span className="hidden sm:inline">Acting as</span>
              <select aria-label="Acting as user" value={uid} onChange={(e) => { setCurrentUserId(e.target.value); setUid(e.target.value); window.location.reload(); }} className="max-w-[220px] rounded-md border border-ink-200 bg-white px-2 py-1 text-ink-900">
                {(users.length ? users : [{ id: uid, display_name: uid, roles: [] }]).map((u) => <option key={u.id} value={u.id}>{u.display_name} ({u.roles.join("/")})</option>)}
              </select>
            </label>
          </div>
        </div>
        {open && (
          <nav id="mobile-nav" className="border-t border-ink-200 bg-white px-4 py-2 lg:hidden" aria-label="Primary mobile">
            {NAV.map((n) => <Link key={n.href} href={n.href} onClick={() => setOpen(false)} className={`block rounded-md px-2 py-2 text-sm ${active(n.href) ? "bg-accent-bg text-accent-fg" : "text-ink-700"}`}>{n.label}</Link>)}
          </nav>
        )}
      </header>
      <main id="main" className="mx-auto w-full max-w-[1600px] flex-1 px-4 py-4">{children}</main>
      <footer className="border-t border-ink-200 bg-ink-50 px-4 py-2 text-center text-[11px] text-ink-500">SI is the source of truth. Seven fields compared deterministically. AI proposes, humans approve. Every action audited.</footer>
    </div>
  );
}
