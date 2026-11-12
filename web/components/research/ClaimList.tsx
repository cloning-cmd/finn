"use client";
import type { Claim, Source } from "@/lib/types";

export type OpenSources = (headline: string, sources: Source[], focus?: string) => void;

/** Resolve a claim's source ids against the dossier's source list (unknown ids are dropped, never invented). */
export function resolve(ids: string[], all: Source[]): Source[] {
  const by = new Map(all.map((s) => [s.id, s]));
  return ids.map((id) => by.get(id)).filter((s): s is Source => Boolean(s));
}

function shortLabel(s: Source): string {
  const l = s.label.replace(/^Annual report /, "AR ").replace(/^Concall /, "Call ").replace("screener.in tables", "screener");
  return s.page ? `${l} p.${s.page}` : l;
}

/** Claims as plain sentences with one source chip each; unverified claims are never shown. */
export default function ClaimList({ claims, sources, onOpen, empty }: { claims: Claim[]; sources: Source[]; onOpen: OpenSources; empty?: string }) {
  const shown = claims.filter((c) => c.verified);
  if (!shown.length) return empty ? <p className="text-[12.5px] text-muted">{empty}</p> : null;
  return (
    <ul className="space-y-1.5">
      {shown.map((c, i) => {
        const src = resolve(c.source_ids, sources);
        return (
          <li key={i} className="text-[13.5px] leading-snug">
            <span>{c.text}</span>
            {src.length > 0 && (
              <button onClick={() => onOpen(c.text, src, src[0].id)} className="ml-1.5 inline-block rounded-full border border-line px-1.5 py-px align-middle text-[10.5px] text-muted">
                {shortLabel(src[0])}{src.length > 1 ? ` +${src.length - 1}` : ""}
              </button>
            )}
          </li>
        );
      })}
    </ul>
  );
}
