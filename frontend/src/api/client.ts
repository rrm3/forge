import type { Session, Message, UserProfile, JournalEntry, Idea, DepartmentConfig, Tip, TipComment, UserIdea, AdminUserSummary, AdminUserIntake } from './types';

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

export async function getPublicProfile(userId: string): Promise<{ user_id: string; name: string; title: string; department: string; avatar_url: string; team: string }> {
  const res = await fetchWithAuth(`${API_BASE}/api/profile/${encodeURIComponent(userId)}`);
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

export async function resetIntake(): Promise<void> {
  const res = await fetchWithAuth(`${API_BASE}/api/profile/reset-intake`, {
    method: 'POST',
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

// Admin API

export async function getAdminAccess(): Promise<{ is_admin: boolean; is_department_admin: boolean; departments: string[] }> {
  const res = await fetchWithAuth(`${API_BASE}/api/admin/access`);
  await checkResponse(res);
  return res.json();
}

export async function getDepartmentConfig(department: string): Promise<DepartmentConfig> {
  const res = await fetchWithAuth(`${API_BASE}/api/admin/departments/${encodeURIComponent(department)}`);
  await checkResponse(res);
  return res.json();
}

export async function saveDepartmentConfig(department: string, config: DepartmentConfig): Promise<void> {
  const res = await fetchWithAuth(`${API_BASE}/api/admin/departments/${encodeURIComponent(department)}`, {
    method: 'PUT',
    body: JSON.stringify(config),
  });
  await checkResponse(res);
}

export async function listAdminUsers(): Promise<AdminUserSummary[]> {
  const res = await fetchWithAuth(`${API_BASE}/api/admin/users`);
  await checkResponse(res);
  return res.json();
}

export async function setUserRole(userId: string, isDepartmentAdmin: boolean): Promise<void> {
  const res = await fetchWithAuth(`${API_BASE}/api/admin/users/${encodeURIComponent(userId)}/role`, {
    method: 'PUT',
    body: JSON.stringify({ is_department_admin: isDepartmentAdmin }),
  });
  await checkResponse(res);
}

export async function setUserAdmin(userId: string, isAdmin: boolean): Promise<void> {
  const res = await fetchWithAuth(`${API_BASE}/api/admin/users/${encodeURIComponent(userId)}/admin`, {
    method: 'PUT',
    body: JSON.stringify({ is_admin: isAdmin }),
  });
  await checkResponse(res);
}

export async function deleteAdminUser(userId: string): Promise<void> {
  const res = await fetchWithAuth(`${API_BASE}/api/admin/users/${encodeURIComponent(userId)}`, {
    method: 'DELETE',
  });
  await checkResponse(res);
}

export async function getAdminUserIntake(userId: string): Promise<AdminUserIntake> {
  const res = await fetchWithAuth(`${API_BASE}/api/admin/users/${encodeURIComponent(userId)}/intake`);
  await checkResponse(res);
  return res.json();
}

export async function listAdminDepartments(): Promise<string[]> {
  const res = await fetchWithAuth(`${API_BASE}/api/admin/departments`);
  await checkResponse(res);
  return res.json();
}

// Tips API

export async function listTips(params?: {
  department?: string;
  sort_by?: 'recent' | 'popular';
  limit?: number;
}): Promise<Tip[]> {
  const query = new URLSearchParams();
  if (params?.department) query.set('department', params.department);
  if (params?.sort_by) query.set('sort_by', params.sort_by);
  if (params?.limit) query.set('limit', params.limit.toString());
  const qs = query.toString();
  const res = await fetchWithAuth(`${API_BASE}/api/tips${qs ? '?' + qs : ''}`);
  await checkResponse(res);
  return res.json();
}

export async function createTip(tip: { title: string; content: string; tags: string[]; department: string }): Promise<Tip> {
  const res = await fetchWithAuth(`${API_BASE}/api/tips`, {
    method: 'POST',
    body: JSON.stringify(tip),
  });
  await checkResponse(res);
  return res.json();
}

export async function getTip(tipId: string): Promise<Tip> {
  const res = await fetchWithAuth(`${API_BASE}/api/tips/${encodeURIComponent(tipId)}`);
  await checkResponse(res);
  return res.json();
}

export async function updateTip(tipId: string, fields: { title?: string; content?: string; tags?: string[]; department?: string }): Promise<Tip> {
  const res = await fetchWithAuth(`${API_BASE}/api/tips/${encodeURIComponent(tipId)}`, {
    method: 'PATCH',
    body: JSON.stringify(fields),
  });
  await checkResponse(res);
  return res.json();
}

export async function deleteTip(tipId: string): Promise<void> {
  const res = await fetchWithAuth(`${API_BASE}/api/tips/${encodeURIComponent(tipId)}`, { method: 'DELETE' });
  await checkResponse(res);
}

export async function voteTip(tipId: string): Promise<void> {
  const res = await fetchWithAuth(`${API_BASE}/api/tips/${encodeURIComponent(tipId)}/vote`, { method: 'POST' });
  await checkResponse(res);
}

export async function unvoteTip(tipId: string): Promise<void> {
  const res = await fetchWithAuth(`${API_BASE}/api/tips/${encodeURIComponent(tipId)}/vote`, { method: 'DELETE' });
  await checkResponse(res);
}

export async function listTipComments(tipId: string): Promise<TipComment[]> {
  const res = await fetchWithAuth(`${API_BASE}/api/tips/${encodeURIComponent(tipId)}/comments`);
  await checkResponse(res);
  return res.json();
}

export async function addTipComment(tipId: string, content: string): Promise<TipComment> {
  const res = await fetchWithAuth(`${API_BASE}/api/tips/${encodeURIComponent(tipId)}/comments`, {
    method: 'POST',
    body: JSON.stringify({ content }),
  });
  await checkResponse(res);
  return res.json();
}

export async function updateTipComment(tipId: string, commentId: string, content: string): Promise<TipComment> {
  const res = await fetchWithAuth(
    `${API_BASE}/api/tips/${encodeURIComponent(tipId)}/comments/${encodeURIComponent(commentId)}`,
    { method: 'PATCH', body: JSON.stringify({ content }) },
  );
  await checkResponse(res);
  return res.json();
}

export async function deleteTipComment(tipId: string, commentId: string): Promise<void> {
  const res = await fetchWithAuth(
    `${API_BASE}/api/tips/${encodeURIComponent(tipId)}/comments/${encodeURIComponent(commentId)}`,
    { method: 'DELETE' },
  );
  await checkResponse(res);
}

// User Ideas API

export async function listUserIdeas(): Promise<UserIdea[]> {
  const res = await fetchWithAuth(`${API_BASE}/api/user-ideas`);
  await checkResponse(res);
  return res.json();
}

export async function createUserIdea(idea: { title: string; description: string; tags: string[]; source?: string; source_session_id?: string }): Promise<UserIdea> {
  const res = await fetchWithAuth(`${API_BASE}/api/user-ideas`, {
    method: 'POST',
    body: JSON.stringify(idea),
  });
  await checkResponse(res);
  return res.json();
}

export async function updateUserIdea(ideaId: string, fields: { title?: string; description?: string; tags?: string[]; status?: string }): Promise<UserIdea> {
  const res = await fetchWithAuth(`${API_BASE}/api/user-ideas/${encodeURIComponent(ideaId)}`, {
    method: 'PUT',
    body: JSON.stringify(fields),
  });
  await checkResponse(res);
  return res.json();
}

export async function deleteUserIdea(ideaId: string): Promise<void> {
  const res = await fetchWithAuth(`${API_BASE}/api/user-ideas/${encodeURIComponent(ideaId)}`, { method: 'DELETE' });
  await checkResponse(res);
}
