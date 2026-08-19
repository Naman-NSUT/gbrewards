import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';

import { logout as logoutRequest } from '../api/auth';
import { setOnSessionChanged, setTokens } from '../api/client';
import type { DealerBrief, StaffOut, TokenPair } from '../api/types';
import { drain, setActiveDealer } from '../offline/queue';
import {
  clearAuth,
  loadSession,
  loadTokens,
  saveSession,
  saveTokens,
  type StoredSession,
} from './tokenStore';

interface AuthState {
  isReady: boolean;
  isAuthenticated: boolean;
  staff: StaffOut | null;
  dealer: DealerBrief | null;
  signIn: (tokens: TokenPair) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthState | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isReady, setReady] = useState(false);
  const [authed, setAuthed] = useState(false);
  const [session, setSession] = useState<StoredSession | null>(null);

  useEffect(() => {
    // Token rotation happens inside the axios client, which has no React
    // context. This is how the rotated pair gets back to secure storage.
    setOnSessionChanged((tokens) => {
      if (!tokens) {
        void clearAuth();
        setSession(null);
        setActiveDealer(null);
        setAuthed(false);
        return;
      }
      void saveTokens({
        accessToken: tokens.access_token,
        refreshToken: tokens.refresh_token,
      });
      if (tokens.staff && tokens.dealer) {
        const next = { staff: tokens.staff, dealer: tokens.dealer };
        setSession(next);
        setActiveDealer(tokens.dealer.id);
        void saveSession(next);
      }
      setAuthed(true);
    });

    void (async () => {
      const [stored, storedSession] = await Promise.all([loadTokens(), loadSession()]);
      if (stored) {
        setTokens(stored);
        setSession(storedSession);
        setActiveDealer(storedSession?.dealer.id ?? null);
        setAuthed(true);
      }
      setReady(true);
    })();
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      isReady,
      isAuthenticated: authed,
      staff: session?.staff ?? null,
      dealer: session?.dealer ?? null,
      signIn: async (tokens) => {
        setTokens({ accessToken: tokens.access_token, refreshToken: tokens.refresh_token });
        await saveTokens({
          accessToken: tokens.access_token,
          refreshToken: tokens.refresh_token,
        });
        if (tokens.staff && tokens.dealer) {
          const next = { staff: tokens.staff, dealer: tokens.dealer };
          setSession(next);
          setActiveDealer(tokens.dealer.id);
          await saveSession(next);
        }
        setAuthed(true);
        // Sales queued before the session expired can go now.
        void drain();
      },
      signOut: async () => {
        const stored = await loadTokens();
        if (stored) {
          // Best effort: revoking the refresh token server-side is good hygiene,
          // but a dealer on a dead connection must still be able to sign out.
          await logoutRequest(stored.refreshToken).catch(() => undefined);
        }
        setTokens(null);
        await clearAuth();
        setSession(null);
        setActiveDealer(null);
        setAuthed(false);
      },
    }),
    [isReady, authed, session]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
