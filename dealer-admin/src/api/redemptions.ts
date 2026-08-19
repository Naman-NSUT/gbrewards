import { api } from './client';
import type { Page, RedemptionDecision, RedemptionRow, RedemptionStatus } from './types';

export interface RedemptionsQuery {
  status?: RedemptionStatus;
  dealer_id?: string;
  limit?: number;
  offset?: number;
}

export async function listRedemptions(params: RedemptionsQuery): Promise<Page<RedemptionRow>> {
  const resp = await api.get<Page<RedemptionRow>>('/dealer-admin/redemptions', { params });
  return resp.data;
}

/** Approval is where the points actually leave the balance (redemption_debit). */
export async function approveRedemption(
  id: string,
  body: { note?: string | null },
): Promise<RedemptionDecision> {
  const resp = await api.post<RedemptionDecision>(`/dealer-admin/redemptions/${id}/approve`, body);
  return resp.data;
}

export async function rejectRedemption(
  id: string,
  body: { reason: string },
): Promise<RedemptionDecision> {
  const resp = await api.post<RedemptionDecision>(`/dealer-admin/redemptions/${id}/reject`, body);
  return resp.data;
}

/** `mark-fulfilled` on the server — the reward physically went out. */
export async function markRedemptionFulfilled(
  id: string,
  body: { note?: string | null },
): Promise<RedemptionDecision> {
  const resp = await api.post<RedemptionDecision>(`/dealer-admin/redemptions/${id}/mark-fulfilled`, body);
  return resp.data;
}
