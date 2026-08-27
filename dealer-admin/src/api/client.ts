import axios from 'axios';
import type { AxiosRequestConfig, AxiosResponse, InternalAxiosRequestConfig } from 'axios';

import { clearTokens, loadTokens, saveTokens, type StoredTokens } from '../auth/tokenStore';
import { API_BASE_URL, API_PREFIX } from '../config';
import type { ApiError, TokenPair } from './types';

/**
 * Every rejection that leaves this module is an ApiRequestError, so call sites
 * never poke at `error.response.data.error.message` and never have to guess
 * whether they are holding an axios error, a network failure or a domain error.
 */
export class ApiRequestError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details: Record<string, unknown>;

  constructor(code: string, message: string, status: number, details: Record<string, unknown>) {
    super(message);
    this.name = 'ApiRequestError';
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

// Hydrate from storage at module load so a page reload keeps the session.
setTokens(loadTokens());

export const api = axios.create({
  baseURL: `${API_BASE_URL}${API_PREFIX}`,
  timeout: 30000,
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

// One refresh in flight at a time. Six queries failing together must not fire
// six refreshes — the backend rotates and burns the refresh token on each
// exchange, so the last five would race into a genuine logout.
let refreshing: Promise<boolean> | null = null;

async function doRefresh(): Promise<boolean> {
  if (!refreshToken) return false;
  try {
    const resp = await axios.post<TokenPair>(
      `${API_BASE_URL}${API_PREFIX}/dealer/auth/admin/refresh`,
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

function toApiError(error: unknown): ApiRequestError {
  if (!axios.isAxiosError(error)) {
    return new ApiRequestError('unknown_error', 'Something went wrong', 0, {});
  }
  const status = error.response?.status ?? 0;
  const envelope = (error.response?.data as { error?: ApiError } | undefined)?.error;
  if (envelope) {
    return new ApiRequestError(
      envelope.code,
      envelope.message,
      status,
      envelope.details ?? {},
    );
  }
  if (error.code === 'ECONNABORTED') {
    return new ApiRequestError('timeout', 'The server took too long to respond', status, {});
  }
  if (status === 0) {
    return new ApiRequestError('network_error', 'Cannot reach the server', 0, {});
  }
  return new ApiRequestError('http_error', error.message || `Request failed (${status})`, status, {});
}

/**
 * Refuse a 2xx whose body is not JSON, loudly.
 *
 * This panel is one of three apps served from a single Vercel origin whose last
 * rewrite in the root vercel.json is `{"source": "/(.*)", "destination":
 * "/index.html"}`; the panel itself is served by the rule above it,
 * `/dealer/(.*)` -> `/dealer/index.html`. Every path that is not a built asset
 * therefore answers 200 text/html with a SPA shell. API_BASE_URL defaults to the
 * literal 'http://localhost:8000', so a production deploy that forgets
 * VITE_API_BASE_URL either hits nothing at all or, once someone "helpfully"
 * points it at the panel's own URL, hits that catch-all.
 *
 * axios makes that quieter than fetch does, not louder: with silentJSONParsing
 * on (the default) it tries JSON.parse itself, swallows the SyntaxError and hands
 * the raw HTML through as `response.data`. Nothing throws. `resp.data
 * .access_token` is undefined, the string "undefined" is stored as the token,
 * every later request goes out as `Bearer undefined`, and the panel loops between
 * the dashboard and the login screen without ever showing an error. Catching it
 * here turns that into one sentence naming the cause.
 *
 * Blob downloads (the printable label sheet) legitimately are not JSON, hence the
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
  throw new ApiRequestError('invalid_response', diagnosis, response.status, {
    contentType,
    url,
  });
}

api.interceptors.response.use(
  // Throwing from the success handler skips the rejection handler beside it —
  // axios chains them as one then(fulfilled, rejected) — so an ApiRequestError
  // raised here reaches the caller as-is rather than being re-wrapped.
  (r) => assertJson(r),
  async (error: unknown) => {
    if (!axios.isAxiosError(error)) return Promise.reject(toApiError(error));

    const original = error.config as (Retriable & InternalAxiosRequestConfig) | undefined;
    const status = error.response?.status;
    const isAuthCall = original?.url?.includes('/auth/');

    if (status === 401 && original && !original._retried && !isAuthCall && refreshToken) {
      original._retried = true;
      refreshing = refreshing ?? doRefresh();
      const ok = await refreshing;
      refreshing = null;
      if (ok) {
        original.headers.Authorization = `Bearer ${accessToken}`;
        return api.request(original);
      }
      clearTokens();
      setTokens(null);
      onLogout?.();
    }
    return Promise.reject(toApiError(error));
  },
);

// The diagnosis on the error is written for whoever is reading the console. This
// is what the operator staring at the screen needs: what is broken and who fixes it.
const INVALID_RESPONSE_MESSAGE =
  'This panel is talking to the website instead of the API, so nothing can load. ' +
  'The deployment is missing VITE_API_BASE_URL — send this to whoever deployed it. ' +
  'The browser console has the details.';

export function apiErrorMessage(error: unknown, fallback = 'Something went wrong'): string {
  if (apiErrorCode(error) === 'invalid_response') return INVALID_RESPONSE_MESSAGE;
  if (error instanceof ApiRequestError) return error.message;
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

export function apiErrorCode(error: unknown): string | null {
  return error instanceof ApiRequestError ? error.code : null;
}
