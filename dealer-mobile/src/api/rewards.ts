import { api } from './client';
import type { CatalogueOut, RedemptionOut, RedemptionPage } from './types';

/**
 * The catalogue, WITH the balance it was priced against.
 *
 * Both of these endpoints return an envelope, not a bare array. Typing them as
 * arrays did not fail loudly — it handed a plain object to a FlatList and to
 * .map(), which is what took the Rewards screen down the moment it opened.
 */
export async function listRewards(): Promise<CatalogueOut> {
  const resp = await api.get<CatalogueOut>('/dealer/rewards');
  return resp.data;
}

export async function listRedemptions(): Promise<RedemptionOut[]> {
  const resp = await api.get<RedemptionPage>('/dealer/redemptions');
  return resp.data.items;
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
