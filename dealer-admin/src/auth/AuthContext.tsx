import { createContext, use, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';

import { claimsFromToken } from '../api/auth';
import { setOnLogout, setTokens } from '../api/client';
import type { AdminProfile, TokenPair } from '../api/types';
import { clearTokens, loadProfile, loadTokens, saveProfile, saveTokens } from './tokenStore';

interface AuthState {
  admin: AdminProfile | null;
  isAuthenticated: boolean;
  /** Convenience for the few owner-only controls. The server enforces it too. */
  isOwner: boolean;
  canWrite: boolean;
  signIn: (pair: TokenPair, email: string) => void;
  signOut: () => void;
  updateAdmin: (patch: Partial<AdminProfile>) => void;
}

const AuthContext = createContext<AuthState | undefined>(undefined);

/**
 * Identity comes from the access token's own claims, so the panel knows its
 * role before any request is made and a cold reload never flashes a wrong nav.
 * `/admin/me` (see hooks/useAccount) enriches the display name afterwards.
 */
function profileFromToken(pair: TokenPair, email: string): AdminProfile {
  const claims = claimsFromToken(pair.access_token);
  return {
    id: claims?.sub ?? 'unknown',
    email,
    name: email.split('@')[0] || email,
    role: claims?.role ?? 'staff',
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [admin, setAdmin] = useState<AdminProfile | null>(() =>
    loadTokens() ? loadProfile<AdminProfile>() : null,
  );

  const signOut = useMemo(
    () => () => {
      clearTokens();
      setTokens(null);
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
      isOwner: admin?.role === 'owner',
      canWrite: admin?.role === 'owner' || admin?.role === 'staff',
      signIn: (pair, email) => {
        const tokens = { accessToken: pair.access_token, refreshToken: pair.refresh_token };
        setTokens(tokens);
        saveTokens(tokens);
        const profile = profileFromToken(pair, email);
        saveProfile(profile);
        setAdmin(profile);
      },
      signOut,
      updateAdmin: (patch) =>
        setAdmin((prev) => {
          if (!prev) return prev;
          const next = { ...prev, ...patch };
          saveProfile(next);
          return next;
        }),
    }),
    [admin, signOut],
  );

  return <AuthContext value={value}>{children}</AuthContext>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthState {
  const ctx = use(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
