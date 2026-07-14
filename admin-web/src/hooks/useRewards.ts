import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  createReward,
  deleteReward,
  listRewards,
  updateReward,
} from '../api/rewards';
import type { RewardInput } from '../api/types';

export function useRewards() {
  return useQuery({ queryKey: ['rewards'], queryFn: listRewards });
}

export function useCreateReward() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: RewardInput) => createReward(input),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['rewards'] }),
  });
}

export function useUpdateReward() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: Partial<RewardInput> }) =>
      updateReward(id, input),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['rewards'] }),
  });
}

export function useDeleteReward() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteReward(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['rewards'] }),
  });
}
