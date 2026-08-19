import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  createReward,
  deleteReward,
  listRewards,
  updateReward,
  type RewardsQuery,
} from '../api/rewards';
import type { RewardInput } from '../api/types';
import { qk } from './keys';

export function useRewards(params: RewardsQuery = {}) {
  return useQuery({
    queryKey: qk.rewardList(params),
    queryFn: () => listRewards(params),
    placeholderData: keepPreviousData,
  });
}

function useRewardMutation<TArgs>(fn: (args: TArgs) => Promise<unknown>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: qk.rewards });
      // A catalogue edit does not reprice requests already in the queue (the
      // points are frozen on the redemption row), but the queue shows names.
      void qc.invalidateQueries({ queryKey: qk.redemptions });
    },
  });
}

export function useCreateReward() {
  return useRewardMutation((body: RewardInput) => createReward(body));
}

export function useUpdateReward() {
  return useRewardMutation(({ id, body }: { id: string; body: Partial<RewardInput> }) =>
    updateReward(id, body),
  );
}

export function useDeleteReward() {
  return useRewardMutation((id: string) => deleteReward(id));
}
