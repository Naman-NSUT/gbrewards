import { api } from './client';
import type { LedgerPage, Me } from './types';

export async function getMe(): Promise<Me> {
  const resp = await api.get<Me>('/me');
  return resp.data;
}

export interface ProfileUpdate {
  name?: string;
  address?: string;
}

export async function updateProfile(payload: ProfileUpdate): Promise<Me> {
  const resp = await api.patch<Me>('/me', payload);
  return resp.data;
}

export async function getLedger(cursor?: string, limit = 20): Promise<LedgerPage> {
  const resp = await api.get<LedgerPage>('/me/ledger', {
    params: { cursor, limit },
  });
  return resp.data;
}
