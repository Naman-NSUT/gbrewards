import { api } from './client';

export interface Reward {
  id: string;
  title: string;
  description: string | null;
  points_cost: number;
  image_url: string | null;
  is_active: boolean;
  sort_order: number;
}

export async function listRewards(): Promise<Reward[]> {
  const resp = await api.get<Reward[]>('/rewards');
  return resp.data;
}
