import { api } from './client';
import type { LedgerEntryOut, LedgerPage, PointsSummary } from './types';

export async function getPointsSummary(): Promise<PointsSummary> {
  const resp = await api.get<PointsSummary>('/dealer/points');
  return resp.data;
}

export async function listLedger(limit = 50, offset = 0): Promise<LedgerEntryOut[]> {
  // A page, not a bare array — the same envelope the rewards endpoints use.
  // Typed as an array this handed a plain object to the Points screen's
  // FlatList, which is a crash rather than an empty list.
  const resp = await api.get<LedgerPage>('/dealer/ledger', {
    params: { limit, offset },
  });
  return resp.data.items;
}
