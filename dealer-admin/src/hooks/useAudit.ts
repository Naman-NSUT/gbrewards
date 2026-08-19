import { keepPreviousData, useQuery } from '@tanstack/react-query';

import { getAuditFilters, listAudit, type AuditQuery } from '../api/audit';
import { qk } from './keys';

export function useAudit(params: AuditQuery) {
  return useQuery({
    queryKey: qk.auditList(params),
    queryFn: () => listAudit(params),
    placeholderData: keepPreviousData,
  });
}

/** The action and entity-type dropdowns: their own endpoint, so the options do
 *  not shrink to whatever happens to be on the current page. */
export function useAuditFilters() {
  return useQuery({
    queryKey: qk.auditFilters(),
    queryFn: getAuditFilters,
    staleTime: 5 * 60 * 1000,
  });
}
