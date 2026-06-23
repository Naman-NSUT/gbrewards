import { useMutation, useQueryClient } from '@tanstack/react-query';

import { claim } from '../api/scan';
import type { ScanClaimResult } from '../api/types';

export function useClaim() {
  const qc = useQueryClient();
  return useMutation<ScanClaimResult, unknown, string>({
    mutationFn: (token: string) => claim(token),
    onSuccess: () => {
      // Balance/history changed — refetch.
      void qc.invalidateQueries({ queryKey: ['me'] });
      void qc.invalidateQueries({ queryKey: ['ledger'] });
    },
  });
}
