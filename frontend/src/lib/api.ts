export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function getToken(): string | null {
  try {
    return localStorage.getItem("auth_token");
  } catch {
    return null;
  }
}

interface FetchOptions extends RequestInit {
  /** Skip auth header */
  noAuth?: boolean;
}

/**
 * Authenticated fetch wrapper.
 * - Auto-attaches Bearer token
 * - 401 → clears token, redirects to /
 * - Throws on non-ok responses
 */
export async function apiFetch<T = unknown>(
  path: string,
  options: FetchOptions = {},
): Promise<T> {
  const { noAuth, headers: extraHeaders, ...rest } = options;
  const token = noAuth ? null : getToken();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...Object.fromEntries(
      Object.entries(extraHeaders ?? {}).filter(([, v]) => v != null) as [string, string][],
    ),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE_URL}${path}`, { headers, ...rest });

  if (res.status === 401) {
    localStorage.removeItem("auth_token");
    window.location.href = "/";
    throw new Error("Unauthorized");
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? res.statusText);
  }

  return res.json() as Promise<T>;
}

/**
 * Fetch with mock fallback — tries API first, falls back to mock data if request fails.
 * Use during development when backend is unavailable.
 */
export async function apiFetchWithFallback<T>(
  path: string,
  fallback: T,
  options: FetchOptions = {},
): Promise<T> {
  try {
    return await apiFetch<T>(path, options);
  } catch {
    return fallback;
  }
}
