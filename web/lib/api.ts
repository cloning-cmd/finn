import type { Brief, Dossier, Rule, Alert } from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

async function j<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API_URL}${path}`, { ...init, headers: { "content-type": "application/json", ...(init?.headers || {}) } });
  if (!r.ok) throw new Error(`${r.status} ${path}`);
  return r.json() as Promise<T>;
}

export const api = {
  brief: (window = "24h", fixture = false) => j<Brief>(`/brief?window=${window}${fixture ? "&fixture=1" : ""}`),
  feedback: (card_id: string, action: "noted" | "less", ticker?: string, category?: string) =>
    j<{ ok: boolean }>("/feedback", { method: "POST", body: JSON.stringify({ card_id, action, ticker, category }) }),
  alerts: () => j<Alert[]>("/alerts"),
  rules: () => j<Rule[]>("/rules"),
  research: (ticker: string) => j<Dossier>(`/research/${ticker}`),
  health: () => j<{ ok: boolean; db: boolean; as_of: string }>("/health"),
};
