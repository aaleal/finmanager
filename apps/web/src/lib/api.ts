/**
 * API client.
 *
 * Cookie-based session + double-submit CSRF token. The token is held in memory
 * only and refreshed from `/auth/me` and from every entity switch.
 */

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly code?: string,
    readonly extra?: Record<string, unknown>,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

let csrfToken: string | null = null;
const listeners = new Set<() => void>();

export function setCsrfToken(token: string | null) {
  csrfToken = token;
}

export function getCsrfToken() {
  return csrfToken;
}

export function onUnauthorized(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

const BASE = '/api';
const UNSAFE = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

type QueryValue = string | number | boolean | null | undefined;

type RequestOptions = {
  method?: string;
  body?: unknown;
  query?: Record<string, QueryValue | QueryValue[]>;
  formData?: FormData;
  signal?: AbortSignal;
};

function buildUrl(path: string, query?: RequestOptions['query']) {
  const url = `${BASE}${path}`;
  if (!query) return url;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    // A repeated key, not a comma-joined one: that is the only shape FastAPI
    // reads back as a list.
    for (const item of Array.isArray(value) ? value : [value]) {
      if (item === undefined || item === null || item === '') continue;
      params.append(key, String(item));
    }
  }
  const qs = params.toString();
  return qs ? `${url}?${qs}` : url;
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? 'GET';
  const headers: Record<string, string> = {};

  if (UNSAFE.has(method) && csrfToken) headers['X-CSRF-Token'] = csrfToken;
  if (options.body !== undefined) headers['Content-Type'] = 'application/json';

  const response = await fetch(buildUrl(path, options.query), {
    method,
    headers,
    credentials: 'same-origin',
    signal: options.signal,
    body:
      options.formData ?? (options.body !== undefined ? JSON.stringify(options.body) : undefined),
  });

  await throwIfError(response);

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

async function throwIfError(response: Response): Promise<void> {
  if (response.status === 401) {
    listeners.forEach((listener) => listener());
  }

  if (!response.ok) {
    let message = `Erro ${response.status}`;
    let code: string | undefined;
    let extra: Record<string, unknown> | undefined;
    try {
      const payload = await response.json();
      if (typeof payload?.detail === 'string') message = payload.detail;
      else if (Array.isArray(payload?.detail)) {
        message = payload.detail
          .map((item: { msg?: string }) => item?.msg ?? '')
          .filter(Boolean)
          .join(' · ');
      }
      code = payload?.code;
      extra = payload;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(response.status, message, code, extra);
  }
}

/**
 * POST a JSON body and read back an NDJSON stream (one JSON value per line),
 * calling `onItem` as each line arrives — lets a slow, per-row backend job
 * (e.g. lego bulk import commit) show live progress instead of one final
 * result. Resolves with every parsed item once the stream ends.
 */
export async function streamNdjson<T>(
  path: string,
  body: unknown,
  onItem: (item: T) => void,
  signal?: AbortSignal,
): Promise<T[]> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (csrfToken) headers['X-CSRF-Token'] = csrfToken;

  const response = await fetch(buildUrl(path), {
    method: 'POST',
    headers,
    credentials: 'same-origin',
    signal,
    body: JSON.stringify(body),
  });

  await throwIfError(response);

  const items: T[] = [];
  const reader = response.body?.getReader();
  if (!reader) return items;

  const decoder = new TextDecoder();
  let buffer = '';
  const consume = (line: string) => {
    const trimmed = line.trim();
    if (!trimmed) return;
    const item = JSON.parse(trimmed) as T;
    items.push(item);
    onItem(item);
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let newlineIndex: number;
    while ((newlineIndex = buffer.indexOf('\n')) >= 0) {
      consume(buffer.slice(0, newlineIndex));
      buffer = buffer.slice(newlineIndex + 1);
    }
  }
  consume(buffer);
  return items;
}

export const api = {
  get: <T>(path: string, query?: RequestOptions['query']) => request<T>(path, { query }),
  post: <T>(path: string, body?: unknown, query?: RequestOptions['query']) =>
    request<T>(path, { method: 'POST', body, query }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: 'PATCH', body }),
  put: <T>(path: string, body?: unknown, query?: RequestOptions['query']) =>
    request<T>(path, { method: 'PUT', body, query }),
  upload: <T>(
    path: string,
    formData: FormData,
    query?: RequestOptions['query'],
    method: 'PUT' | 'POST' = 'PUT',
  ) => request<T>(path, { method, formData, query }),
  delete: <T>(path: string, query?: RequestOptions['query']) =>
    request<T>(path, { method: 'DELETE', query }),
  download: (path: string, query?: RequestOptions['query']) => download(path, query),
};

/**
 * Fetch a binary attachment and hand it to the browser as a file.
 *
 * Going through `fetch` rather than a plain `<a href>` keeps the download on the
 * same error path as every other call, so a 401 still triggers the re-login flow.
 */
export async function download(path: string, query?: RequestOptions['query']): Promise<void> {
  const response = await fetch(buildUrl(path, query), { credentials: 'same-origin' });

  if (response.status === 401) listeners.forEach((listener) => listener());
  if (!response.ok) throw new ApiError(response.status, `Erro ${response.status}`);

  const disposition = response.headers.get('Content-Disposition') ?? '';
  const match = /filename="?([^"]+)"?/.exec(disposition);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = match?.[1] ?? 'download';
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
