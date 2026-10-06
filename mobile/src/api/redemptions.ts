import { api } from './client';
import type { Redemption } from './types';

export async function createRedemption(points: number): Promise<Redemption> {
  const resp = await api.post<Redemption>('/redemptions', { points });
  return resp.data;
}

/**
 * Request `quantity` lots of one reward. The server prices it from the reward's
 * own points_cost and holds the whole amount, so the caller never sends points.
 */
export async function redeemReward(rewardId: string, quantity = 1): Promise<Redemption> {
  const resp = await api.post<Redemption>('/redemptions', {
    reward_id: rewardId,
    quantity,
  });
  return resp.data;
}

export async function listRedemptions(): Promise<Redemption[]> {
  const resp = await api.get<Redemption[]>('/redemptions');
  return resp.data;
}

export async function cancelRedemption(id: string): Promise<Redemption> {
  const resp = await api.delete<Redemption>(`/redemptions/${id}`);
  return resp.data;
}
