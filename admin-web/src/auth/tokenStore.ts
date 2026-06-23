const ACCESS_KEY = 'sr_admin_access';
const REFRESH_KEY = 'sr_admin_refresh';

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
}
