import { api } from './client';
import type { Reward, RewardInput } from './types';

export async function listRewards(): Promise<Reward[]> {
  const resp = await api.get<Reward[]>('/admin/rewards');
  return resp.data;
}

export async function createReward(input: RewardInput): Promise<Reward> {
  const resp = await api.post<Reward>('/admin/rewards', input);
  return resp.data;
}

export async function updateReward(id: string, input: Partial<RewardInput>): Promise<Reward> {
  const resp = await api.patch<Reward>(`/admin/rewards/${id}`, input);
  return resp.data;
}

export async function deleteReward(id: string): Promise<void> {
  await api.delete(`/admin/rewards/${id}`);
}
