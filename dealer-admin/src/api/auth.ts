import { api } from './client';
import type { AdminProfile, AdminRole, TokenPair } from './types';

export async function login(email: string, password: string): Promise<TokenPair> {
  const resp = await api.post<TokenPair>('/auth/admin/login', { email, password });
  return resp.data;
}

export async function fetchProfile(): Promise<AdminProfile> {
  const resp = await api.get<AdminProfile>('/dealer-admin/me');
  return resp.data;
}

interface AccessClaims {
  sub: string;
  role?: AdminRole;
  exp?: number;
}

function decodeSegment(segment: string): unknown {
  const padded = segment.replace(/-/g, '+').replace(/_/g, '/');
  const json = atob(padded.padEnd(padded.length + ((4 - (padded.length % 4)) % 4), '='));
  return JSON.parse(json);
}

/**
 * The admin token carries `sub` and `role`, so the panel knows who it is signed
 * in as the instant login returns — no second round-trip before the first paint,
 * and no blank screen if `/dealer-admin/me` is momentarily unavailable.
 *
 * This is display-layer only. The server re-checks the role on every mutation
 * (require_admin_write / require_owner); nothing here grants anything.
 */
export function claimsFromToken(token: string): AccessClaims | null {
  const parts = token.split('.');
  if (parts.length !== 3) return null;
  try {
    const payload = decodeSegment(parts[1]) as Partial<AccessClaims>;
    return payload.sub ? { sub: payload.sub, role: payload.role, exp: payload.exp } : null;
  } catch {
    return null;
  }
}
