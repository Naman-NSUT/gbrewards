const ACCESS_KEY = 'dr_admin_access';
const REFRESH_KEY = 'dr_admin_refresh';
const PROFILE_KEY = 'dr_admin_profile';

export interface StoredTokens {
  accessToken: string;
  refreshToken: string;
}

export function loadTokens(): StoredTokens | null {
  const accessToken = localStorage.getItem(ACCESS_KEY);
  const refreshToken = localStorage.getItem(REFRESH_KEY);
  if (accessToken && refreshToken) return { accessToken, refreshToken };
  return null;
}

export function saveTokens(tokens: StoredTokens): void {
  localStorage.setItem(ACCESS_KEY, tokens.accessToken);
  localStorage.setItem(REFRESH_KEY, tokens.refreshToken);
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
  localStorage.removeItem(PROFILE_KEY);
}

export function loadProfile<T>(): T | null {
  const raw = localStorage.getItem(PROFILE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

export function saveProfile(profile: unknown): void {
  localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
}
