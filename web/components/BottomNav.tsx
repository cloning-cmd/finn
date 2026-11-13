"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { href: "/", label: "Brief", icon: "M4 5.5h16M4 10.5h16M4 15.5h10M4 20h6" },
  { href: "/alerts", label: "Alerts", icon: "M15 17h5l-1.4-1.4A2 2 0 0 1 18 14.2V11a6 6 0 0 0-4-5.7V5a2 2 0 1 0-4 0v.3A6 6 0 0 0 6 11v3.2c0 .5-.2 1-.6 1.4L4 17h5m6 0v1a3 3 0 1 1-6 0v-1" },
  { href: "/research", label: "Research", icon: "M21 21l-4.3-4.3M17 10.5a6.5 6.5 0 1 1-13 0 6.5 6.5 0 0 1 13 0z" },
  { href: "/rules", label: "Rules", icon: "M4 7h9M17 7h3M4 17h3M11 17h9M15 5v4M9 15v4" },
];

/** Floating tab bar; the active tab gets a filled pill behind its icon. */
export default function BottomNav() {
  const path = usePathname();
  return (
    <nav className="fixed inset-x-0 bottom-0 z-40 px-3" style={{ paddingBottom: "calc(env(safe-area-inset-bottom, 0px) + 10px)" }}>
      <ul className="mx-auto flex max-w-[440px] items-stretch rounded-[22px] border border-line bg-surface/90 p-1.5 shadow-[0_8px_30px_rgb(0_0_0/0.25)] backdrop-blur-xl">
        {TABS.map((t) => {
          const active = t.href === "/" ? path === "/" : path.startsWith(t.href);
          return (
            <li key={t.href} className="flex-1">
              <Link href={t.href} aria-current={active ? "page" : undefined}
                className={`flex h-12 flex-col items-center justify-center gap-0.5 rounded-2xl text-[10.5px] font-medium transition-colors ${active ? "bg-accent/12 text-accent" : "text-muted hover:text-fg"}`}>
                <svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={active ? 2.1 : 1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={t.icon} /></svg>
                {t.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
