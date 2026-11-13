"use client";
import type { Claim, Source } from "@/lib/types";

export type OpenSources = (headline: string, sources: Source[], focus?: string) => void;

/** Resolve a claim's source ids against the dossier's source list (unknown ids are dropped, never invented). */
export function resolve(ids: string[], all: Source[]): Source[] {
  const by = new Map(all.map((s) => [s.id, s]));
  return ids.map((id) => by.get(id)).filter((s): s is Source => Boolean(s));
}

function shortLabel(s: Source): string {
  const l = s.label.replace(/^Annual report /, "AR ").replace(/^Concall /, "Call ").replace("screener.in tables", "Screener");
  return s.page ? `${l} p.${s.page}` : l;
}

/** Claims as plain sentences with one source chip each; unverified claims are never shown. */
export default function ClaimList({ claims, sources, onOpen, empty, dense = false }: { claims: Claim[]; sources: Source[]; onOpen: OpenSources; empty?: string; dense?: boolean }) {
  const shown = claims.filter((c) => c.verified);
  if (!shown.length) return empty ? <p className="text-[13px] text-muted">{empty}</p> : null;
  return (
    <ul className={dense ? "space-y-2" : "space-y-3"}>
      {shown.map((c, i) => {
        const src = resolve(c.source_ids, sources);
        return (
          <li key={i} className="flex gap-2.5 text-[13.5px] leading-relaxed">
            <span className="mt-[9px] h-1 w-1 shrink-0 rounded-full bg-faint" aria-hidden="true" />
            <span>
              {c.text}
              {src.length > 0 && (
                <button onClick={() => onOpen(c.text, src, src[0].id)}
                  className="ml-1.5 inline-flex translate-y-[-1px] items-center rounded-md bg-surface-2 px-1.5 py-0.5 align-middle text-[10.5px] font-medium text-muted transition-colors hover:bg-accent/12 hover:text-accent">
                  {shortLabel(src[0])}{src.length > 1 ? ` +${src.length - 1}` : ""}
                </button>
              )}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
