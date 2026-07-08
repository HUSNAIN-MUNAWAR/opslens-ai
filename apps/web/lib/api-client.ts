export type JsonValue = string | number | boolean | null | JsonObject | JsonValue[];
export type JsonObject = { [key: string]: JsonValue };

const DEFAULT_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';
const TOKEN_KEY = 'opslens.phase3.access_token';
const REFRESH_KEY = 'opslens.phase3.refresh_token';

export type ApiEnvelope<T> = {
  data: T | null;
  error: string | null;
  requestId: string | null;
};

export function apiBaseUrl() {
  return DEFAULT_BASE_URL.replace(/\/$/, '');
}

export function readAccessToken() {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function writeTokens(accessToken: string, refreshToken?: string) {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(TOKEN_KEY, accessToken);
  if (refreshToken) window.localStorage.setItem(REFRESH_KEY, refreshToken);
}

export async function ensureDemoSession(email = 'admin@opslens.demo') {
  const existing = readAccessToken();
  if (existing) return existing;
  const response = await fetch(`${apiBaseUrl()}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Request-ID': `web-${Date.now()}` },
    body: JSON.stringify({ email, password: 'DemoPass123!' }),
  });
  if (!response.ok) throw new Error(`Demo login failed (${response.status})`);
  const payload = (await response.json()) as { access_token: string; refresh_token?: string };
  writeTokens(payload.access_token, payload.refresh_token);
  return payload.access_token;
}

export async function apiFetch<T = JsonValue>(path: string, init: RequestInit = {}): Promise<ApiEnvelope<T>> {
  try {
    const token = await ensureDemoSession();
    const headers = new Headers(init.headers);
    headers.set('Authorization', `Bearer ${token}`);
    headers.set('Content-Type', headers.get('Content-Type') ?? 'application/json');
    headers.set('X-Request-ID', headers.get('X-Request-ID') ?? `web-${Date.now()}`);
    const response = await fetch(`${apiBaseUrl()}${path}`, { ...init, headers });
    const requestId = response.headers.get('x-request-id');
    const text = await response.text();
    const data = text ? JSON.parse(text) as T : null;
    if (!response.ok) {
      const detail = typeof data === 'object' && data !== null && 'detail' in data ? String((data as { detail: unknown }).detail) : `Request failed (${response.status})`;
      return { data: null, error: detail, requestId };
    }
    return { data, error: null, requestId };
  } catch (error) {
    return { data: null, error: error instanceof Error ? error.message : 'API unavailable', requestId: null };
  }
}

export function summarizeJson(value: JsonValue | null): string {
  if (value === null) return 'No payload returned.';
  return JSON.stringify(value, null, 2).slice(0, 1800);
}
