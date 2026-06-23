import { api } from './client';
import type { ScanClaimResult } from './types';

export async function claim(token: string): Promise<ScanClaimResult> {
  const resp = await api.post<ScanClaimResult>('/scan/claim', { token });
  return resp.data;
}
