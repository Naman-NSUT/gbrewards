import { api } from './client';
import type { Ok, Page, RewardInput, RewardRow } from './types';

export interface RewardsQuery {
  is_active?: boolean;
  limit?: number;
  offset?: number;
}

/** Paginated on the server like every other list, even though it is short. */
export async function listRewards(params: RewardsQuery = {}): Promise<Page<RewardRow>> {
  const resp = await api.get<Page<RewardRow>>('/dealer-admin/rewards', { params });
  return resp.data;
}

export async function getReward(id: string): Promise<RewardRow> {
  const resp = await api.get<RewardRow>(`/dealer-admin/rewards/${id}`);
  return resp.data;
}

export async function createReward(body: RewardInput): Promise<RewardRow> {
  const resp = await api.post<RewardRow>('/dealer-admin/rewards', body);
  return resp.data;
}

export async function updateReward(id: string, body: Partial<RewardInput>): Promise<RewardRow> {
  const resp = await api.patch<RewardRow>(`/dealer-admin/rewards/${id}`, body);
  return resp.data;
}

export async function deleteReward(id: string): Promise<Ok> {
  const resp = await api.delete<Ok>(`/dealer-admin/rewards/${id}`);
  return resp.data;
}
