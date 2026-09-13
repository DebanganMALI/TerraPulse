// same-origin by default, proxied to the backend by vite (see vite.config.ts).
// set VITE_API_BASE to an absolute url to point at someone else's machine.
const BASE = import.meta.env.VITE_API_BASE ?? "/api/v1";
export const STATIC_BASE = import.meta.env.VITE_STATIC_BASE ?? "";

export class ApiError extends Error {
  code?: string;
  status: number;
  constructor(message: string, status: number, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

// kept in a module variable rather than localStorage: nothing to exfiltrate via XSS
let token: string | null = null;
export const setToken = (t: string | null) => {
  token = t;
};

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(BASE + path, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...init.headers,
      },
    });
  } catch {
    throw new ApiError("Cannot reach the API. Is the backend running?", 0, "NETWORK");
  }

  if (res.status === 204) return undefined as T;

  if (!res.ok) {
    const body = await res.json().catch(() => ({}) as any);
    throw new ApiError(body.detail ?? res.statusText, res.status, body.code);
  }
  return res.json();
}

export const staticUrl = (p: string) => STATIC_BASE + p;
