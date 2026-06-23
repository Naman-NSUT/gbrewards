import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';

import { setOnLogout, setTokens } from '../api/client';
import type { Admin, AdminTokenPair } from '../api/types';
import { clearTokens, loadTokens, saveTokens } from './tokenStore';

const ADMIN_KEY = 'sr_admin_profile';

interface AuthState {
  admin: Admin | null;
  isAuthenticated: boolean;
  signIn: (pair: AdminTokenPair) => void;
  signOut: () => void;
  updateAdmin: (patch: Partial<Admin>) => void;
}

const AuthContext = createContext<AuthState | undefined>(undefined);

function loadAdmin(): Admin | null {
  const raw = localStorage.getItem(ADMIN_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Admin;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [admin, setAdmin] = useState<Admin | null>(() =>
    loadTokens() ? loadAdmin() : null,
  );

  const signOut = useMemo(
    () => () => {
      clearTokens();
      setTokens(null);
      localStorage.removeItem(ADMIN_KEY);
      setAdmin(null);
    },
    [],
  );

  useEffect(() => {
    // The axios interceptor calls this when a refresh ultimately fails.
    setOnLogout(signOut);
  }, [signOut]);

  const value = useMemo<AuthState>(
    () => ({
      admin,
      isAuthenticated: admin !== null,
      signIn: (pair) => {
        const tokens = { accessToken: pair.access_token, refreshToken: pair.refresh_token };
        setTokens(tokens);
        saveTokens(tokens);
        localStorage.setItem(ADMIN_KEY, JSON.stringify(pair.admin));
        setAdmin(pair.admin);
      },
      signOut,
      updateAdmin: (patch) =>
        setAdmin((prev) => {
          if (!prev) return prev;
          const next = { ...prev, ...patch };
          localStorage.setItem(ADMIN_KEY, JSON.stringify(next));
          return next;
        }),
    }),
    [admin, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
