// axios re-exports `create`/`isAxiosError` as both default members and named
// exports; using them off the default import is intentional here.
/* eslint-disable import/no-named-as-default-member */
import axios, {
  AxiosError,
  AxiosRequestConfig,
  InternalAxiosRequestConfig,
} from 'axios';

import { API_BASE_URL, API_PREFIX } from '../config';
import type { StoredTokens } from '../auth/tokenStore';
import type { ApiError, TokenPair } from './types';

// In-memory auth state, kept in sync with secure-store by AuthContext.
let accessToken: string | null = null;
let refreshToken: string | null = null;
let onTokensChanged: ((tokens: StoredTokens | null) => void) | null = null;

export function setTokens(tokens: StoredTokens | null): void {
  accessToken = tokens?.accessToken ?? null;
  refreshToken = tokens?.refreshToken ?? null;
}

export function setOnTokensChanged(cb: (tokens: StoredTokens | null) => void): void {
  onTokensChanged = cb;
}

export const api = axios.create({
  baseURL: `${API_BASE_URL}${API_PREFIX}`,
  // Generous timeout so a cold-started backend (free-tier hosts spin down and
  // take 30–60s to wake) doesn't abort a request the server actually completes.
  timeout: 60000,
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

let refreshing: Promise<boolean> | null = null;

async function doRefresh(): Promise<boolean> {
  if (!refreshToken) return false;
  try {
    const resp = await axios.post<TokenPair>(
      `${API_BASE_URL}${API_PREFIX}/auth/refresh`,
      { refresh_token: refreshToken },
      { headers: { 'Content-Type': 'application/json' } }
    );
    const next: StoredTokens = {
      accessToken: resp.data.access_token,
      refreshToken: resp.data.refresh_token,
    };
    setTokens(next);
    onTokensChanged?.(next);
    return true;
  } catch {
    setTokens(null);
    onTokensChanged?.(null);
    return false;
  }
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<{ error?: ApiError }>) => {
    const original = error.config as (RetriableConfig & InternalAxiosRequestConfig) | undefined;
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
    }
    return Promise.reject(error);
  }
);

export function extractApiError(error: unknown): ApiError | null {
  if (axios.isAxiosError(error)) {
    return (error.response?.data as { error?: ApiError } | undefined)?.error ?? null;
  }
  return null;
}
