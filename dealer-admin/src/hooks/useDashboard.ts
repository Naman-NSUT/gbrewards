import { useQuery } from '@tanstack/react-query';

import { getDashboardAnalytics, getDashboardStats } from '../api/dashboard';
import { qk } from './keys';

export function useDashboardStats() {
  return useQuery({
    queryKey: qk.dashboardStats(),
    queryFn: getDashboardStats,
    // The morning routine is "open it, glance, act". A minute of staleness is
    // invisible; a refetch on every tab focus is not.
    staleTime: 60 * 1000,
  });
}

export function useDashboardAnalytics(days: number) {
  return useQuery({
    queryKey: qk.dashboardAnalytics(days),
    queryFn: () => getDashboardAnalytics(days),
    staleTime: 60 * 1000,
  });
}
