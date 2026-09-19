"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api, currentUserId, setCurrentUserId } from "@/lib/api";

type Me = { id: string; display_name: string; roles: string[]; permissions: string[] };

const NAV = [
  { href: "/", label: "Inbox", icon: "inbox" },
  { href: "/verification", label: "Seven fields", icon: "check" },
  { href: "/security", label: "Security", icon: "shield" },
  { href: "/agent", label: "AI agent", icon: "spark" },
  { href: "/audit", label: "Audit", icon: "audit" },
  { href: "/policies", label: "Policies", icon: "policy" },
  { href: "/welcome", label: "Guide", icon: "guide" },
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
    <div className="dashboard-surface flex min-h-screen flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-white focus:px-3 focus:py-2">Skip to content</a>
      <header className="sticky top-0 z-40 h-16 border-b border-ink-200/80 bg-white/90 backdrop-blur-xl lg:fixed lg:left-0 lg:top-0 lg:h-screen lg:w-64 lg:border-b-0 lg:border-r">
        <div className="mx-auto flex h-full max-w-[1600px] items-center gap-4 px-4 lg:mx-0 lg:flex-col lg:items-stretch lg:gap-6 lg:px-5 lg:py-7">
          <Link href="/" className="flex shrink-0 items-center" aria-label="NovaShip Averis home">
            <img src="/novaship-logo-clean.png" alt="NovaShip" className="h-auto w-[122px] lg:w-[132px]" />
          </Link>
          <nav className="hidden items-center gap-0.5 text-sm lg:flex lg:w-full lg:flex-col" aria-label="Primary">
            {NAV.map((n, i) => (
              <div key={n.href} className="w-full">
                <Link href={n.href} aria-current={active(n.href) ? "page" : undefined} className={`dashboard-number flex items-center gap-3 whitespace-nowrap rounded-xl px-3 py-2.5 text-[15px] font-semibold transition duration-200 hover:translate-x-1 ${active(n.href) ? "bg-accent-bg text-accent-fg ring-1 ring-accent-ring/50" : "text-ink-700 hover:bg-[#fff0e5] hover:text-accent-fg"}`}><NavIcon name={n.icon} />{n.label}</Link>
              </div>
            ))}
          </nav>
          <button className="rounded-md border border-ink-200 px-2 py-1 text-xs text-ink-700 lg:hidden" onClick={() => setOpen(!open)} aria-expanded={open} aria-controls="mobile-nav">Menu</button>
          <div className="ml-auto flex items-center gap-3 text-xs lg:mt-auto lg:ml-0 lg:w-full lg:max-w-full lg:flex-col lg:items-stretch lg:rounded-2xl lg:border lg:border-[#eaded3] lg:bg-[#fbf7f2] lg:p-2.5">
            <span className={`hidden items-center gap-1.5 whitespace-nowrap xl:flex ${health ? "text-match" : "text-mismatch"}`} title={health ? `repository: ${health.backend}` : "backend unreachable"}>
              <span className={`h-2 w-2 rounded-full ${health ? "bg-match" : "bg-mismatch"}`} aria-hidden />{health ? `API online, ${health.cases} cases` : "API offline"}
            </span>
            <label className="flex min-w-0 items-center gap-2 text-ink-500 lg:flex-col lg:items-stretch lg:gap-1.5">
              <span className="hidden font-semibold text-ink-700 sm:inline lg:block">Acting as</span>
              <select aria-label="Acting as user" value={uid} onChange={(e) => { setCurrentUserId(e.target.value); setUid(e.target.value); window.location.reload(); }} className="max-w-[220px] rounded-md border border-ink-200 bg-white px-2 py-1 text-ink-900 lg:w-full lg:max-w-full">
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
      <main id="main" className="mx-auto w-full max-w-[1600px] flex-1 px-4 py-6 lg:ml-64 lg:w-[calc(100%-16rem)] lg:max-w-none lg:px-8 lg:py-8">{children}</main>
      <footer className="border-t border-ink-200/80 bg-white/60 px-4 py-3 text-center text-[11px] text-ink-500 lg:ml-64 lg:w-[calc(100%-16rem)]">SI is the source of truth. Seven fields compared deterministically. AI proposes, humans approve. Every action audited.</footer>
    </div>
  );
}

function NavIcon({ name }: { name: string }) {
  const paths: Record<string, React.ReactNode> = {
    inbox: <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="M3 9h5l2 3h4l2-3h5" /></>,
    check: <><rect x="4" y="3" width="16" height="18" rx="2" /><path d="m8 12 2.5 2.5L16 9" /></>,
    shield: <path d="M12 3 19 6v5c0 4.7-3 7.9-7 10-4-2.1-7-5.3-7-10V6l7-3Z" />,
    spark: <path d="m12 2 1.9 6.1L20 10l-6.1 1.9L12 18l-1.9-6.1L4 10l6.1-1.9L12 2Zm7 14 .8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8L19 16Z" />,
    audit: <><path d="M6 3h9l3 3v15H6z" /><path d="M9 11h6M9 15h6M9 19h4" /></>,
    policy: <><path d="M12 3 4 6v5c0 5 3.4 8.5 8 10 4.6-1.5 8-5 8-10V6l-8-3Z" /><path d="m9 12 2 2 4-4" /></>,
    guide: <><circle cx="12" cy="12" r="8" /><path d="M12 10v5M12 7h.01" /></>,
  };
  return <svg viewBox="0 0 24 24" className="h-5 w-5 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>{paths[name]}</svg>;
}
