import { useQuery } from '@tanstack/react-query';

import { getAnalytics, getAudit, getDashboard, getScans } from '../api/reporting';

export function useDashboard() {
  return useQuery({ queryKey: ['dashboard'], queryFn: getDashboard });
}

export function useAnalytics() {
  return useQuery({ queryKey: ['analytics'], queryFn: getAnalytics });
}

export function useScans(params: {
  product_id?: string;
  user_id?: string;
  from?: string;
  to?: string;
  cursor?: string;
}) {
  return useQuery({
    queryKey: ['scans', params],
    queryFn: () => getScans(params),
  });
}

export function useAudit(params: {
  entity?: string;
  actor?: string;
  from?: string;
  to?: string;
  cursor?: string;
}) {
  return useQuery({
    queryKey: ['audit', params],
    queryFn: () => getAudit(params),
  });
}
