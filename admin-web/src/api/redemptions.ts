import { api } from './client';
import type { Redemption, RedemptionStatus } from './types';

export async function listRedemptions(status?: RedemptionStatus): Promise<Redemption[]> {
  const resp = await api.get<Redemption[]>('/admin/redemptions', {
    params: status ? { status } : {},
  });
  return resp.data;
}

type Action = 'approve' | 'reject' | 'fulfill';

export async function actOnRedemption(
  id: string,
  action: Action,
  note?: string,
): Promise<Redemption> {
  const resp = await api.post<Redemption>(`/admin/redemptions/${id}/${action}`, { note });
  return resp.data;
}
