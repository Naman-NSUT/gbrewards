import { api } from './client';
import type { CompliancePage, ComplianceDetail, DealerStatus } from './types';

/** The sort keys the server actually accepts — services/compliance._SORTS. */
export type ComplianceSort =
  | 'worst'
  | 'rate'
  | 'self_registrations'
  | 'unregistered'
  | 'quietest'
  | 'slowest'
  | 'allocated'
  | 'registered'
  | 'name'
  | 'code';

export interface ComplianceQuery {
  date_from?: string;
  date_to?: string;
  status?: DealerStatus;
  q?: string;
  /** Hides dealers who were never sent anything — they cannot have a rate. */
  with_stock_only?: boolean;
  /** Server-side so paging stays correct: page 3 of "worst first" must be real. */
  sort?: ComplianceSort;
  limit?: number;
  offset?: number;
}

export async function listCompliance(params: ComplianceQuery): Promise<CompliancePage> {
  const resp = await api.get<CompliancePage>('/dealer-admin/compliance', { params });
  return resp.data;
}

export async function getComplianceDetail(
  dealerId: string,
  params: { date_from?: string; date_to?: string; limit?: number },
): Promise<ComplianceDetail> {
  const resp = await api.get<ComplianceDetail>(`/dealer-admin/compliance/dealers/${dealerId}`, {
    params,
  });
  return resp.data;
}
