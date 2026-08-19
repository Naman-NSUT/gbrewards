// Deliberately the SAME keys the worker panel uses.
//
// Both panels authenticate the same `admins` row with the same aud='admin'
// token, and both are served from one origin, so sharing the keys means
// switching panels carries the session instead of dumping the operator at a
// second login. Using the worker panel's existing names (rather than a new
// shared one) means no admin currently signed in gets logged out by this.
const ACCESS_KEY = 'sr_admin_access';
const REFRESH_KEY = 'sr_admin_refresh';
// Display-only cache of who is signed in; dealer-panel specific, so it keeps
// its own key.
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
