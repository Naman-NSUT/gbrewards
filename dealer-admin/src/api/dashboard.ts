import { api } from './client';
import type { DashboardAnalytics, DashboardStats } from './types';

export async function getDashboardStats(): Promise<DashboardStats> {
  const resp = await api.get<DashboardStats>('/dealer-admin/dashboard');
  return resp.data;
}

export async function getDashboardAnalytics(days: number): Promise<DashboardAnalytics> {
  const resp = await api.get<DashboardAnalytics>('/dealer-admin/dashboard/analytics', {
    params: { days },
  });
  return resp.data;
}
