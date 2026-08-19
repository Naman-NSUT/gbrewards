import { keepPreviousData, useQuery } from '@tanstack/react-query';

import { getComplianceDetail, listCompliance, type ComplianceQuery } from '../api/compliance';
import { qk } from './keys';

export function useCompliance(params: ComplianceQuery) {
  return useQuery({
    queryKey: qk.complianceList(params),
    queryFn: () => listCompliance(params),
    // Keeps the previous page on screen while the next one loads, so changing
    // the date window doesn't blank a table the client is reading down.
    placeholderData: keepPreviousData,
  });
}

export function useComplianceDetail(
  dealerId: string | null,
  params: { date_from?: string; date_to?: string; limit?: number },
) {
  return useQuery({
    queryKey: qk.complianceDetail(dealerId, params),
    queryFn: () => getComplianceDetail(dealerId as string, params),
    enabled: dealerId !== null,
  });
}
