// axios re-exports `create`/`isAxiosError` as both default members and named
// exports; using them off the default import is intentional here.
/* eslint-disable import/no-named-as-default-member */
import axios, { AxiosError, AxiosRequestConfig, InternalAxiosRequestConfig } from 'axios';

import type { StoredTokens } from '../auth/tokenStore';
import { API_BASE_URL, API_PREFIX, REQUEST_TIMEOUT_MS } from '../config';
import type { ApiError, TokenPair } from './types';

// In-memory auth state, kept in sync with secure-store by AuthContext. Held in a
// module rather than in React state so the offline queue — which drains from a
// background timer with no component mounted — can still authenticate.
let accessToken: string | null = null;
let refreshToken: string | null = null;
let onSessionChanged: ((tokens: TokenPair | null) => void) | null = null;

export function setTokens(tokens: StoredTokens | null): void {
  accessToken = tokens?.accessToken ?? null;
  refreshToken = tokens?.refreshToken ?? null;
}

export function hasTokens(): boolean {
  return accessToken !== null;
}

export function setOnSessionChanged(cb: (tokens: TokenPair | null) => void): void {
  onSessionChanged = cb;
}

/**
 * A failure with the backend's `{error:{code,message,details}}` envelope already
 * unwrapped, so no screen has to reach into an AxiosError.
 *
 * `status === null` means the request never reached the server (offline, DNS,
 * timeout). The offline queue keys its retry-vs-fail decision on that
 * distinction, so it is modelled explicitly rather than inferred at each site.
 */
export class ApiRequestError extends Error {
  readonly code: string;
  readonly status: number | null;
  readonly details: Record<string, unknown>;
  readonly retryAfterMs: number | null;

  constructor(
    code: string,
    message: string,
    status: number | null,
    details: Record<string, unknown> = {},
    retryAfterMs: number | null = null
  ) {
    super(message);
    this.name = 'ApiRequestError';
    this.code = code;
    this.status = status;
    this.details = details;
    this.retryAfterMs = retryAfterMs;
  }

  /** True when the request never got an answer — retrying is worthwhile. */
  get isNetworkFailure(): boolean {
    return this.status === null;
  }
}

export function isApiError(error: unknown): error is ApiRequestError {
  return error instanceof ApiRequestError;
}

/** The error code, for callers that only branch on it. */
export function errorCode(error: unknown): string | null {
  return isApiError(error) ? error.code : null;
}

/** A message safe to show a dealer, for any thrown value. */
export function errorMessage(error: unknown, fallback = 'Something went wrong'): string {
  if (isApiError(error)) return error.message;
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

export const api = axios.create({
  baseURL: `${API_BASE_URL}${API_PREFIX}`,
  timeout: REQUEST_TIMEOUT_MS,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (accessToken && !config.headers.Authorization) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

interface RetriableConfig extends AxiosRequestConfig {
  _retried?: boolean;
}

// Single-flight: a burst of parallel 401s must produce one refresh, not five —
// and the loser of that race would otherwise burn a rotated refresh token.
let refreshing: Promise<boolean> | null = null;

async function doRefresh(): Promise<boolean> {
  if (!refreshToken) return false;
  try {
    const resp = await axios.post<TokenPair>(
      `${API_BASE_URL}${API_PREFIX}/dealer/auth/refresh`,
      { refresh_token: refreshToken },
      { headers: { 'Content-Type': 'application/json' }, timeout: REQUEST_TIMEOUT_MS }
    );
    setTokens({
      accessToken: resp.data.access_token,
      refreshToken: resp.data.refresh_token,
    });
    onSessionChanged?.(resp.data);
    return true;
  } catch (error) {
    // Only a definitive rejection ends the session. A refresh that failed
    // because the shop's wifi dropped must not sign the dealer out mid-sale.
    const status = axios.isAxiosError(error) ? error.response?.status : undefined;
    if (status !== undefined && status >= 400 && status < 500) {
      setTokens(null);
      onSessionChanged?.(null);
    }
    return false;
  }
}

function toApiRequestError(error: AxiosError<{ error?: ApiError }>): ApiRequestError {
  if (error.response) {
    const envelope = error.response.data?.error;
    const retryAfter = Number(error.response.headers?.['retry-after']);
    return new ApiRequestError(
      envelope?.code ?? 'http_error',
      envelope?.message ?? `Request failed (${error.response.status})`,
      error.response.status,
      envelope?.details ?? {},
      Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter * 1000 : null
    );
  }
  if (error.code === 'ECONNABORTED') {
    return new ApiRequestError('timeout', 'The connection timed out', null);
  }
  return new ApiRequestError(
    'network_error',
    'No connection to the GoodBed server',
    null
  );
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<{ error?: ApiError }>) => {
    const original = error.config as (RetriableConfig & InternalAxiosRequestConfig) | undefined;
    const status = error.response?.status;
    const isAuthCall = original?.url?.includes('/dealer/auth/');

    if (status === 401 && original && !original._retried && !isAuthCall && refreshToken) {
      original._retried = true;
      refreshing = refreshing ?? doRefresh();
      const ok = await refreshing;
      refreshing = null;
      if (ok) {
        original.headers.Authorization = `Bearer ${accessToken}`;
        return api.request(original);
      }
    }
    return Promise.reject(toApiRequestError(error));
  }
);
