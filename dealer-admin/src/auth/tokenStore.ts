// Deliberately DIFFERENT keys from the worker panel.
//
// These once matched, back when both panels authenticated the same `admins`
// row with one aud='admin' token. The programmes now have separate operator
// tables and separate audiences: the worker panel mints aud='admin', this one
// mints aud='dealer_admin', and each API rejects the other's token outright.
//
// Both panels are served from one origin, so shared keys meant the panel
// switcher handed each panel a token its own API would 401 on — and because
// ProtectedRoute only checks that a token EXISTS, you were let in and every
// request failed after. Separate keys let both sessions live side by side, so
// switching panels lands you signed in to whichever you actually signed in to.
const ACCESS_KEY = 'dr_admin_access';
const REFRESH_KEY = 'dr_admin_refresh';
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
