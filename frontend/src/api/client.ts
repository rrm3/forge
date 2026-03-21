import type { Session, Message, UserProfile, JournalEntry, Idea } from './types';

let getTokenFn: (() => Promise<string | null>) | null = null;
let tokenGetterReady: (() => void) | null = null;
const tokenGetterPromise = new Promise<void>((resolve) => { tokenGetterReady = resolve; });

export function setTokenGetter(fn: () => Promise<string | null>) {
  getTokenFn = fn;
  tokenGetterReady?.();
}

const API_BASE = import.meta.env.VITE_API_URL || '';

async function fetchWithAuth(url: string, options: RequestInit = {}): Promise<Response> {
  // Wait for the token getter to be wired up (prevents 401 race on startup)
  await tokenGetterPromise;
  const token = await getTokenFn?.();
  const headers = new Headers(options.headers);
  if (token) headers.set('Authorization', `Bearer ${token}`);
  headers.set('Content-Type', 'application/json');

  // Masquerade: forward the target email so the backend swaps identity
  const masquerade = localStorage.getItem('forge-masquerade');
  if (masquerade) headers.set('X-Masquerade-As', masquerade);

  return fetch(url, { ...options, headers });
}

async function checkResponse(res: Response): Promise<Response> {
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res;
}

// Session API

export async function listSessions(): Promise<Session[]> {
  const res = await fetchWithAuth(`${API_BASE}/api/sessions`);
  await checkResponse(res);
  return res.json();
}

export async function createSession(): Promise<Session> {
  const res = await fetchWithAuth(`${API_BASE}/api/sessions`, { method: 'POST', body: '{}' });
  await checkResponse(res);
  return res.json();
}

export async function getSession(id: string): Promise<Session & { transcript: Message[] }> {
  const res = await fetchWithAuth(`${API_BASE}/api/sessions/${encodeURIComponent(id)}`);
  await checkResponse(res);
  return res.json();
}

export async function deleteSession(id: string): Promise<void> {
  const res = await fetchWithAuth(`${API_BASE}/api/sessions/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  });
  await checkResponse(res);
}

export async function renameSession(id: string, title: string): Promise<void> {
  const res = await fetchWithAuth(`${API_BASE}/api/sessions/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: JSON.stringify({ title }),
  });
  await checkResponse(res);
}

// Profile API

export async function getProfile(): Promise<UserProfile> {
  const res = await fetchWithAuth(`${API_BASE}/api/profile`);
  await checkResponse(res);
  return res.json();
}

export async function updateProfile(fields: Partial<UserProfile>): Promise<void> {
  const res = await fetchWithAuth(`${API_BASE}/api/profile`, {
    method: 'PATCH',
    body: JSON.stringify(fields),
  });
  await checkResponse(res);
}

// Journal API

export async function listJournal(params?: {
  date_from?: string;
  date_to?: string;
  limit?: number;
}): Promise<JournalEntry[]> {
  const qs = params ? '?' + new URLSearchParams(
    Object.fromEntries(
      Object.entries(params)
        .filter(([, v]) => v !== undefined)
        .map(([k, v]) => [k, String(v)])
    )
  ).toString() : '';
  const res = await fetchWithAuth(`${API_BASE}/api/journal${qs}`);
  await checkResponse(res);
  return res.json();
}

// Ideas API

export async function listIdeas(params?: {
  status?: string;
  limit?: number;
}): Promise<Idea[]> {
  const qs = params ? '?' + new URLSearchParams(
    Object.fromEntries(
      Object.entries(params)
        .filter(([, v]) => v !== undefined)
        .map(([k, v]) => [k, String(v)])
    )
  ).toString() : '';
  const res = await fetchWithAuth(`${API_BASE}/api/ideas${qs}`);
  await checkResponse(res);
  return res.json();
}
