import { api } from './client';
import type { CompliancePage, ComplianceDetail, DealerStatus } from './types';

/**
 * The sort keys the server actually accepts — services/compliance._SORTS.
 *
 * Kept in step with that dict deliberately: an unknown key is not ignored, it is
 * a 400 invalid_sort, so a value that exists only here ships a broken dropdown.
 * 'rate', 'unregistered', 'slowest' and 'allocated' were removed when stock
 * stopped being scoped to shops — there is no allocated-versus-registered ratio
 * left to rank on.
 */
export type ComplianceSort =
  | 'worst'
  | 'self_registrations'
  | 'quietest'
  | 'registrations'
  | 'backdated'
  | 'registered'
  | 'name'
  | 'code';

export interface ComplianceQuery {
  date_from?: string;
  date_to?: string;
  status?: DealerStatus;
  q?: string;
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
