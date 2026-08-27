import axios from 'axios';
import type { AxiosRequestConfig, AxiosResponse, InternalAxiosRequestConfig } from 'axios';

import { API_BASE_URL, API_PREFIX } from '../config';
import { clearTokens, loadTokens, saveTokens, type StoredTokens } from '../auth/tokenStore';
import type { AdminTokenPair, ApiError } from './types';

/**
 * A response that arrived successfully and was not the API talking.
 *
 * Carries the `{code, message, details}` shape the rest of the panel already
 * reads, so extractApiError() can hand it back like any server envelope.
 */
export class ApiResponseError extends Error implements ApiError {
  readonly code: string;
  readonly status: number;
  readonly details: Record<string, unknown>;

  constructor(code: string, message: string, status: number, details: Record<string, unknown>) {
    super(message);
    this.name = 'ApiResponseError';
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

let accessToken: string | null = null;
let refreshToken: string | null = null;
let onLogout: (() => void) | null = null;

export function setTokens(tokens: StoredTokens | null): void {
  accessToken = tokens?.accessToken ?? null;
  refreshToken = tokens?.refreshToken ?? null;
}

export function setOnLogout(cb: () => void): void {
  onLogout = cb;
}

// Hydrate from storage at module load so refreshes survive a page reload.
setTokens(loadTokens());

export const api = axios.create({
  baseURL: `${API_BASE_URL}${API_PREFIX}`,
  timeout: 20000,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (accessToken && !config.headers.Authorization) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

interface Retriable extends AxiosRequestConfig {
  _retried?: boolean;
}

let refreshing: Promise<boolean> | null = null;

async function doRefresh(): Promise<boolean> {
  if (!refreshToken) return false;
  try {
    const resp = await axios.post<AdminTokenPair>(
      `${API_BASE_URL}${API_PREFIX}/admin/auth/refresh`,
      { refresh_token: refreshToken },
      { headers: { 'Content-Type': 'application/json' } },
    );
    const next: StoredTokens = {
      accessToken: resp.data.access_token,
      refreshToken: resp.data.refresh_token,
    };
    setTokens(next);
    saveTokens(next);
    return true;
  } catch {
    return false;
  }
}

/**
 * Refuse a 2xx whose body is not JSON, loudly.
 *
 * This panel is one of three apps served from a single Vercel origin whose last
 * rewrite in the root vercel.json is `{"source": "/(.*)", "destination":
 * "/index.html"}` — and this panel is what that catch-all serves. Every path that
 * is not a built asset answers 200 text/html with the panel's own shell.
 * API_BASE_URL defaults to the literal 'http://localhost:8000', so a production
 * deploy that forgets VITE_API_BASE_URL either reaches nothing at all or, once
 * someone "helpfully" repoints it at the panel's own URL, reaches that catch-all.
 *
 * axios makes that quieter than fetch does, not louder: with silentJSONParsing
 * on (the default) it tries JSON.parse itself, swallows the SyntaxError and
 * hands the raw HTML through as `response.data`. Nothing throws. `resp.data
 * .access_token` is undefined, signIn() writes the string "undefined" into
 * localStorage as the token, every later request goes out as `Bearer undefined`,
 * and the panel loops between the dashboard and the login screen without ever
 * showing an error. Catching it here turns that into one sentence naming the
 * cause.
 *
 * Blob downloads (QR sheet PDFs) legitimately are not JSON, hence the
 * responseType check; a 204 arrives as an empty string and is not a failure.
 */
function assertJson(response: AxiosResponse): AxiosResponse {
  const expectsJson = !response.config.responseType || response.config.responseType === 'json';
  if (!expectsJson || typeof response.data !== 'string' || response.data === '') return response;

  const contentType = String(response.headers?.['content-type'] ?? 'unknown');
  const url = `${response.config.baseURL ?? ''}${response.config.url ?? ''}`;
  const diagnosis =
    `Expected JSON from ${url} but got ${contentType} (HTTP ${response.status}). ` +
    'VITE_API_BASE_URL is probably unset or pointing at the panel itself instead of ' +
    "the API, so the site's own index.html came back.";
  // The operator gets the sentence from apiErrorMessage(); the console keeps the
  // diagnosis, because only whoever deployed the panel can fix this.
  console.error(`[api] ${diagnosis}`, String(response.data).slice(0, 200));
  throw new ApiResponseError('invalid_response', diagnosis, response.status, {
    contentType,
    url,
  });
}

api.interceptors.response.use(
  (r) => assertJson(r),
  async (error) => {
    if (!axios.isAxiosError(error)) return Promise.reject(error);
    const original = error.config as (Retriable & InternalAxiosRequestConfig) | undefined;
    const status = error.response?.status;
    const isAuthCall = original?.url?.includes('/auth/');

    if (status === 401 && original && !original._retried && !isAuthCall && refreshToken) {
      original._retried = true;
      refreshing = refreshing ?? doRefresh();
      const ok = await refreshing;
      refreshing = null;
      if (ok) {
        original.headers = original.headers ?? {};
        original.headers.Authorization = `Bearer ${accessToken}`;
        return api.request(original);
      }
      clearTokens();
      setTokens(null);
      onLogout?.();
    }
    return Promise.reject(error);
  },
);

export function extractApiError(error: unknown): ApiError | null {
  // Our own throw already IS the envelope shape, so call sites that switch on a
  // code keep working without learning about a second error type.
  if (error instanceof ApiResponseError) return error;
  if (axios.isAxiosError(error)) {
    return (error.response?.data as { error?: ApiError } | undefined)?.error ?? null;
  }
  return null;
}

// The diagnosis on the error is written for whoever is reading the console. This
// is what the operator staring at the screen needs: what is broken and who fixes it.
const INVALID_RESPONSE_MESSAGE =
  'This panel is talking to the website instead of the API, so nothing can load. ' +
  'The deployment is missing VITE_API_BASE_URL — send this to whoever deployed it. ' +
  'The browser console has the details.';

export function apiErrorMessage(error: unknown, fallback = 'Something went wrong'): string {
  const envelope = extractApiError(error);
  if (envelope?.code === 'invalid_response') return INVALID_RESPONSE_MESSAGE;
  return envelope?.message ?? fallback;
}
