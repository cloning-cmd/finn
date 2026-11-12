import type { Brief, Dossier, Rule, Alert, Claim, Source, ProgressEvent } from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");
// Demo-only shared secret for /admin/* (replay a day). Set NEXT_PUBLIC_ADMIN_TOKEN on Vercel to match ADMIN_TOKEN.
export const ADMIN_TOKEN = process.env.NEXT_PUBLIC_ADMIN_TOKEN || "dev";

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
  if (!dossier) throw new Error("The build stopped before it finished: the API connection dropped or the server restarted. Retry in a minute.");
  return dossier;
}

export const api = {
  brief: (window = "24h", fixture = false) => j<Brief>(`/brief?window=${window}${fixture ? "&fixture=1" : ""}`),
  feedback: (card_id: string, action: "noted" | "less", ticker?: string, category?: string) =>
    j<{ ok: boolean }>("/feedback", { method: "POST", body: JSON.stringify({ card_id, action, ticker, category }) }),
  alerts: (limit = 50) => j<Alert[]>(`/alerts?limit=${limit}`),
  evaluateAlerts: (hours = 26) => j<{ cards: number; rules: number; fired: number; pushed: number }>(`/alerts/evaluate?hours=${hours}`, { method: "POST" }),
  rules: () => j<Rule[]>("/rules"),
  saveRule: (rule: Rule) => j<Rule>("/rules", { method: "POST", body: JSON.stringify(rule) }),
  deleteRule: (id: string) => j<{ ok: boolean }>(`/rules/${encodeURIComponent(id)}`, { method: "DELETE" }),
  parseRule: (text: string) => j<{ rule: Rule; method: "rule" | "llm"; cost: number }>("/rules/parse", { method: "POST", body: JSON.stringify({ text }) }),
  replay: (date: string, spacing = 3) => j<{ date: string; cards: number; queued: number }>(`/admin/replay?date=${date}&spacing=${spacing}&token=${encodeURIComponent(ADMIN_TOKEN)}`, { method: "POST" }),
  research: (ticker: string) => j<Dossier>(`/research/${encodeURIComponent(ticker)}`),
  qa: (ticker: string, question: string, card_id?: string) => j<QAResponse>("/qa", { method: "POST", body: JSON.stringify({ ticker, question, card_id }) }),
  health: () => j<{ ok: boolean; db: boolean; as_of: string }>("/health"),
};
