const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8010';
const FETCH_TIMEOUT_MS = 5000;

/**
 * Fetch from the backend API with connection-error safety.
 *
 * Node's fetch() can hang or throw TypeError when the backend is
 * unreachable. This wrapper adds a timeout and catches all errors,
 * returning `fallback` instead of crashing the page.
 */
export async function fetchApi<T>(
  path: string,
  fallback: T,
  init?: RequestInit,
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      cache: 'no-store' as RequestCache,
      signal: controller.signal,
      ...init,
    });
    if (!res.ok) return fallback;
    return res.json();
  } catch {
    return fallback;
  } finally {
    clearTimeout(timer);
  }
}

/**
 * POST/PUT/DELETE to the backend API. Returns { ok, detail } instead
 * of throwing on network errors.
 */
export async function mutateApi(
  path: string,
  init?: RequestInit,
): Promise<{ ok: boolean; detail?: string }> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      signal: controller.signal,
      ...init,
    });
    if (!res.ok) {
      let detail = `Request failed (${res.status})`;
      try {
        const body = await res.json();
        if (body.detail) detail = body.detail;
      } catch {}
      return { ok: false, detail };
    }
    return { ok: true };
  } catch {
    return { ok: false, detail: 'Could not connect to backend' };
  } finally {
    clearTimeout(timer);
  }
}
