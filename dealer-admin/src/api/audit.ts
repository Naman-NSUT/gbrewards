import { api } from './client';
import type { ActorType, AuditFilters, AuditRow, Page } from './types';

export interface AuditQuery {
  actor_type?: ActorType;
  actor_id?: string;
  action?: string;
  entity_type?: string;
  entity_id?: string;
  q?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}

export async function listAudit(params: AuditQuery): Promise<Page<AuditRow>> {
  const resp = await api.get<Page<AuditRow>>('/dealer-admin/audit', { params });
  return resp.data;
}

/** The distinct actions and entity types actually present — the filter options. */
export async function getAuditFilters(): Promise<AuditFilters> {
  const resp = await api.get<AuditFilters>('/dealer-admin/audit/filters');
  return resp.data;
}

/** Everything ever recorded against one entity, newest first. Bare array. */
export async function listAuditForEntity(
  entityType: string,
  entityId: string,
  params: { limit?: number } = {},
): Promise<AuditRow[]> {
  const resp = await api.get<AuditRow[]>(`/dealer-admin/audit/entity/${entityType}/${entityId}`, {
    params,
  });
  return resp.data;
}
