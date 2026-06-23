import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { cancelRedemption, createRedemption, listRedemptions } from '../api/redemptions';
import type { Redemption } from '../api/types';

export function useRedemptions() {
  return useQuery<Redemption[]>({ queryKey: ['redemptions'], queryFn: listRedemptions });
}

export function useCreateRedemption() {
  const qc = useQueryClient();
  return useMutation<Redemption, unknown, number>({
    mutationFn: (points: number) => createRedemption(points),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['me'] });
      void qc.invalidateQueries({ queryKey: ['redemptions'] });
    },
  });
}

export function useCancelRedemption() {
  const qc = useQueryClient();
  return useMutation<Redemption, unknown, string>({
    mutationFn: (id: string) => cancelRedemption(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['me'] });
      void qc.invalidateQueries({ queryKey: ['redemptions'] });
    },
  });
}
