import type { AppConfig, LocalModelsResponse, ProbeResponse } from "../types/settings";

const BACKEND_HTTP_ORIGIN =
  (import.meta.env.VITE_BACKEND_HTTP_ORIGIN as string | undefined)?.trim() ||
  "http://127.0.0.1:8080";
const API_BASE = BACKEND_HTTP_ORIGIN.replace(/\/+$/, "");

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status}: ${text || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export async function getSettings(): Promise<AppConfig> {
  const res = await fetch(`${API_BASE}/settings`);
  return handleResponse<AppConfig>(res);
}

export async function saveSettings(cfg: AppConfig): Promise<AppConfig> {
  const res = await fetch(`${API_BASE}/settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cfg),
  });
  return handleResponse<AppConfig>(res);
}

export async function getLocalModels(): Promise<string[]> {
  const res = await fetch(`${API_BASE}/settings/models/local`);
  const data = await handleResponse<LocalModelsResponse>(res);
  return data.files;
}

export async function probeRemote(base_url: string, api_key: string): Promise<ProbeResponse> {
  const res = await fetch(`${API_BASE}/settings/probe`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ base_url, api_key }),
  });
  return handleResponse<ProbeResponse>(res);
}
