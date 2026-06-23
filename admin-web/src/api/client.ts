import axios from 'axios';
import type { AxiosRequestConfig, InternalAxiosRequestConfig } from 'axios';

import { API_BASE_URL, API_PREFIX } from '../config';
import { clearTokens, loadTokens, saveTokens, type StoredTokens } from '../auth/tokenStore';
import type { AdminTokenPair, ApiError } from './types';

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

api.interceptors.response.use(
  (r) => r,
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
  if (axios.isAxiosError(error)) {
    return (error.response?.data as { error?: ApiError } | undefined)?.error ?? null;
  }
  return null;
}

export function apiErrorMessage(error: unknown, fallback = 'Something went wrong'): string {
  return extractApiError(error)?.message ?? fallback;
}
