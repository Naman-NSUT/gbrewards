import { api } from './client';
import type { LedgerEntryOut, PointsSummary } from './types';

export async function getPointsSummary(): Promise<PointsSummary> {
  const resp = await api.get<PointsSummary>('/dealer/points');
  return resp.data;
}

export async function listLedger(limit = 50, offset = 0): Promise<LedgerEntryOut[]> {
  const resp = await api.get<LedgerEntryOut[]>('/dealer/ledger', {
    params: { limit, offset },
  });
  return resp.data;
}
