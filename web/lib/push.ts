// Web Push client: permission, subscription, iOS detection. All failures resolve to a status, never throw to the UI.
import { API_URL } from "./api";

export type PushStatus = "unsupported" | "ios_needs_install" | "denied" | "off" | "on";

function b64ToUint8(b64: string): Uint8Array {
  const pad = "=".repeat((4 - (b64.length % 4)) % 4);
  const raw = atob((b64 + pad).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

export function isIOS(): boolean {
  if (typeof navigator === "undefined") return false;
  return /iPhone|iPad|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
}

export function isStandalone(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(display-mode: standalone)").matches || (navigator as unknown as { standalone?: boolean }).standalone === true;
}

export async function pushStatus(): Promise<PushStatus> {
  if (typeof window === "undefined" || !("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) {
    return isIOS() && !isStandalone() ? "ios_needs_install" : "unsupported";
  }
  if (Notification.permission === "denied") return "denied";
  try {
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.getSubscription();
    return sub ? "on" : "off";
  } catch { return "off"; }
}

export async function enablePush(): Promise<{ status: PushStatus; error?: string }> {
  const st = await pushStatus();
  if (st === "unsupported" || st === "ios_needs_install" || st === "denied") return { status: st };
  try {
    const perm = await Notification.requestPermission();
    if (perm !== "granted") return { status: perm === "denied" ? "denied" : "off" };
    const r = await fetch(`${API_URL}/push/key`);
    const { public_key, configured } = (await r.json()) as { public_key: string; configured: boolean };
    if (!configured || !public_key) return { status: "off", error: "server has no push keys" };
    const reg = await navigator.serviceWorker.ready;
    const sub = (await reg.pushManager.getSubscription()) ?? (await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64ToUint8(public_key) as BufferSource }));
    const res = await fetch(`${API_URL}/push/subscribe`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(sub.toJSON()) });
    if (!res.ok) return { status: "off", error: `subscribe ${res.status}` };
    await fetch(`${API_URL}/push/test`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ endpoint: sub.endpoint }) }).catch(() => undefined);
    return { status: "on" };
  } catch (e) {
    return { status: "off", error: e instanceof Error ? e.message : String(e) };
  }
}

export async function disablePush(): Promise<PushStatus> {
  try {
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.getSubscription();
    if (sub) {
      await fetch(`${API_URL}/push/subscribe?endpoint=${encodeURIComponent(sub.endpoint)}`, { method: "DELETE" }).catch(() => undefined);
      await sub.unsubscribe();
    }
  } catch { /* ignore */ }
  return "off";
}
