import { api } from './client';
import type { AuditPage, Dashboard, DashboardAnalytics, ScanFeedPage } from './types';

export async function getDashboard(): Promise<Dashboard> {
  const resp = await api.get<Dashboard>('/admin/dashboard');
  return resp.data;
}

export async function getAnalytics(): Promise<DashboardAnalytics> {
  const resp = await api.get<DashboardAnalytics>('/admin/analytics');
  return resp.data;
}

export async function getScans(params: {
  product_id?: string;
  user_id?: string;
  from?: string;
  to?: string;
  cursor?: string;
  limit?: number;
}): Promise<ScanFeedPage> {
  const resp = await api.get<ScanFeedPage>('/admin/scans', { params });
  return resp.data;
}

export async function getAudit(params: {
  entity?: string;
  actor?: string;
  from?: string;
  to?: string;
  cursor?: string;
  limit?: number;
}): Promise<AuditPage> {
  const resp = await api.get<AuditPage>('/admin/audit', { params });
  return resp.data;
}
