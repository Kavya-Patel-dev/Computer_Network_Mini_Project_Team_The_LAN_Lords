const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1').replace(/\/$/, '');

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

function cookie(name: string): string | null {
  const prefix = `${name}=`;
  const row = document.cookie.split('; ').find((item) => item.startsWith(prefix));
  return row ? decodeURIComponent(row.slice(prefix.length)) : null;
}

async function request<T>(path: string, init: RequestInit = {}, timeoutMs = 300_000): Promise<T> {
  const method = (init.method || 'GET').toUpperCase();
  const headers = new Headers(init.headers);
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    const csrf = cookie('lanlords_csrf');
    if (csrf) headers.set('X-CSRF-Token', csrf);
  }
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers,
      credentials: 'include',
      signal: init.signal || controller.signal,
    });
    if (response.status === 204) return undefined as T;
    const contentType = response.headers.get('content-type') || '';
    const payload = contentType.includes('application/json') ? await response.json() : await response.text();
    if (!response.ok) {
      const detail = typeof payload === 'object' && payload && 'detail' in payload
        ? String((payload as { detail: unknown }).detail)
        : `API request failed (${response.status})`;
      throw new ApiError(response.status, detail);
    }
    return payload as T;
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw new Error('The request timed out. Please try again.');
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown, options?: { timeoutMs?: number }) => request<T>(
    path,
    { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) },
    options?.timeoutMs,
  ),
  patch: <T>(path: string, body: unknown) => request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
};

export interface ApiUser {
  id: string;
  name: string;
  email: string;
  role: 'user' | 'admin';
  status: 'active' | 'deactivated';
  created_at: string;
  last_active_at: string | null;
  plansCount?: number;
  sessionsCount?: number;
}

export function toUserProfile(user: ApiUser) {
  return {
    id: user.id,
    name: user.name,
    email: user.email,
    role: user.role,
    status: user.status,
    plansCount: user.plansCount || 0,
    lastActive: user.last_active_at || user.created_at,
    createdAt: user.created_at,
    sessionsCount: user.sessionsCount,
  } as const;
}
