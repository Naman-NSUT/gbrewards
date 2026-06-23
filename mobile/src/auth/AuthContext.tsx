import React, {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';

import { setOnTokensChanged, setTokens } from '../api/client';
import { clearTokens, loadTokens, saveTokens, type StoredTokens } from './tokenStore';

interface AuthState {
  isReady: boolean;
  isAuthenticated: boolean;
  signIn: (tokens: StoredTokens) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthState | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isReady, setReady] = useState(false);
  const [authed, setAuthed] = useState(false);

  useEffect(() => {
    // Refresh-rotation inside the axios client persists new tokens here.
    setOnTokensChanged((tokens) => {
      if (tokens) {
        void saveTokens(tokens);
        setAuthed(true);
      } else {
        void clearTokens();
        setAuthed(false);
      }
    });

    void (async () => {
      const stored = await loadTokens();
      if (stored) {
        setTokens(stored);
        setAuthed(true);
      }
      setReady(true);
    })();
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      isReady,
      isAuthenticated: authed,
      signIn: async (tokens) => {
        setTokens(tokens);
        await saveTokens(tokens);
        setAuthed(true);
      },
      signOut: async () => {
        setTokens(null);
        await clearTokens();
        setAuthed(false);
      },
    }),
    [isReady, authed]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
