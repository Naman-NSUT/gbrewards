import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { actOnRedemption, listRedemptions } from '../api/redemptions';
import type { RedemptionStatus } from '../api/types';

export function useRedemptions(status?: RedemptionStatus) {
  return useQuery({
    queryKey: ['redemptions', status ?? 'all'],
    queryFn: () => listRedemptions(status),
  });
}

export function useRedemptionAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      action,
      note,
    }: {
      id: string;
      action: 'approve' | 'reject' | 'fulfill';
      note?: string;
    }) => actOnRedemption(id, action, note),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['redemptions'] });
      void qc.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}
