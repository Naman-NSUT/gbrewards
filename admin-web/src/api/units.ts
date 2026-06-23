import { api } from './client';
import type { ReactivateResult, Unit, UnitDetail, UnitStatus } from './types';

export async function listUnits(params: {
  product_id?: string;
  status?: UnitStatus;
  q?: string;
}): Promise<Unit[]> {
  const resp = await api.get<Unit[]>('/admin/units', { params });
  return resp.data;
}

export async function getUnit(token: string): Promise<UnitDetail> {
  const resp = await api.get<UnitDetail>(`/admin/units/${token}`);
  return resp.data;
}

export async function voidUnit(unitId: string): Promise<Unit> {
  const resp = await api.post<Unit>(`/admin/units/${unitId}/void`);
  return resp.data;
}

export async function reactivateUnit(unitId: string): Promise<ReactivateResult> {
  const resp = await api.post<ReactivateResult>(`/admin/units/${unitId}/reactivate`);
  return resp.data;
}
