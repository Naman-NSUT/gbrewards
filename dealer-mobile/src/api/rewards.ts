import { api } from './client';
import type { RedemptionOut, RewardOut } from './types';

export async function listRewards(): Promise<RewardOut[]> {
  const resp = await api.get<RewardOut[]>('/dealer/rewards');
  return resp.data;
}

export async function listRedemptions(): Promise<RedemptionOut[]> {
  const resp = await api.get<RedemptionOut[]>('/dealer/redemptions');
  return resp.data;
}

export async function redeemReward(rewardId: string): Promise<RedemptionOut> {
  const resp = await api.post<RedemptionOut>('/dealer/redemptions', { reward_id: rewardId });
  return resp.data;
}

export async function cancelRedemption(redemptionId: string): Promise<RedemptionOut> {
  const resp = await api.post<RedemptionOut>(
    `/dealer/redemptions/${encodeURIComponent(redemptionId)}/cancel`,
    {}
  );
  return resp.data;
}
