import * as SecureStore from 'expo-secure-store';

import type { DealerBrief, StaffOut } from '../api/types';

const ACCESS_KEY = 'dr_access_token';
const REFRESH_KEY = 'dr_refresh_token';
const SESSION_KEY = 'dr_session';

export interface StoredTokens {
  accessToken: string;
  refreshToken: string;
}

/** Who is signed in. Cached so Profile renders offline, with no /me round-trip. */
export interface StoredSession {
  staff: StaffOut;
  dealer: DealerBrief;
}

export async function loadTokens(): Promise<StoredTokens | null> {
  const [accessToken, refreshToken] = await Promise.all([
    SecureStore.getItemAsync(ACCESS_KEY),
    SecureStore.getItemAsync(REFRESH_KEY),
  ]);
  if (accessToken && refreshToken) return { accessToken, refreshToken };
  return null;
}

export async function saveTokens(tokens: StoredTokens): Promise<void> {
  await Promise.all([
    SecureStore.setItemAsync(ACCESS_KEY, tokens.accessToken),
    SecureStore.setItemAsync(REFRESH_KEY, tokens.refreshToken),
  ]);
}

export async function loadSession(): Promise<StoredSession | null> {
  const raw = await SecureStore.getItemAsync(SESSION_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as StoredSession;
  } catch {
    return null;
  }
}

export async function saveSession(session: StoredSession): Promise<void> {
  await SecureStore.setItemAsync(SESSION_KEY, JSON.stringify(session));
}

export async function clearAuth(): Promise<void> {
  await Promise.all([
    SecureStore.deleteItemAsync(ACCESS_KEY),
    SecureStore.deleteItemAsync(REFRESH_KEY),
    SecureStore.deleteItemAsync(SESSION_KEY),
  ]);
}
