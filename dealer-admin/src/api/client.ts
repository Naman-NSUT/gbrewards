import axios from 'axios';
import type { AxiosRequestConfig, InternalAxiosRequestConfig } from 'axios';

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
      `${API_BASE_URL}${API_PREFIX}/auth/admin/refresh`,
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

api.interceptors.response.use(
  (r) => r,
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

export function apiErrorMessage(error: unknown, fallback = 'Something went wrong'): string {
  if (error instanceof ApiRequestError) return error.message;
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

export function apiErrorCode(error: unknown): string | null {
  return error instanceof ApiRequestError ? error.code : null;
}
