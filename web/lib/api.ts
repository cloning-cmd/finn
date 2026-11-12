import type { Brief, Dossier, Rule, Alert, Claim, Source, ProgressEvent } from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

async function j<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API_URL}${path}`, { ...init, headers: { "content-type": "application/json", ...(init?.headers || {}) } });
  if (!r.ok) throw new Error(`${r.status} ${path}`);
  return r.json() as Promise<T>;
}

export interface QAResponse { claims: Claim[]; sources: Source[]; model: string | null; cost: number; gaps: string[] }

/** POST /research/{ticker} streams SSE (progress events, then one dossier). fetch + ReadableStream since EventSource is GET-only. */
export async function researchStream(ticker: string, onProgress: (e: ProgressEvent) => void, force = false): Promise<Dossier> {
  const r = await fetch(`${API_URL}/research/${encodeURIComponent(ticker)}${force ? "?force=1" : ""}`, { method: "POST", headers: { accept: "text/event-stream" } });
  if (!r.ok || !r.body) throw new Error(`${r.status} research`);
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  let dossier: Dossier | null = null;
  let error: string | null = null;
  const handle = (block: string) => {
    let event = "message";
    const data: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) data.push(line.slice(5).trim());
    }
    if (!data.length) return;
    const payload = data.join("\n");
    if (event === "progress") onProgress(JSON.parse(payload) as ProgressEvent);
    else if (event === "dossier") dossier = JSON.parse(payload) as Dossier;
    else if (event === "error") error = (JSON.parse(payload) as { detail: string }).detail;
  };
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i: number;
    while ((i = buf.indexOf("\n\n")) >= 0) { handle(buf.slice(0, i)); buf = buf.slice(i + 2); }
  }
  if (buf.trim()) handle(buf);
  if (error) throw new Error(error);
  if (!dossier) throw new Error("stream ended without a dossier");
  return dossier;
}

export const api = {
  brief: (window = "24h", fixture = false) => j<Brief>(`/brief?window=${window}${fixture ? "&fixture=1" : ""}`),
  feedback: (card_id: string, action: "noted" | "less", ticker?: string, category?: string) =>
    j<{ ok: boolean }>("/feedback", { method: "POST", body: JSON.stringify({ card_id, action, ticker, category }) }),
  alerts: () => j<Alert[]>("/alerts"),
  rules: () => j<Rule[]>("/rules"),
  research: (ticker: string) => j<Dossier>(`/research/${encodeURIComponent(ticker)}`),
  qa: (ticker: string, question: string, card_id?: string) => j<QAResponse>("/qa", { method: "POST", body: JSON.stringify({ ticker, question, card_id }) }),
  health: () => j<{ ok: boolean; db: boolean; as_of: string }>("/health"),
};
