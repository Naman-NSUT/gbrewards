import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { listRewards, type Reward } from '../api/rewards';
import { redeemReward } from '../api/redemptions';
import type { Redemption } from '../api/types';

export function useRewards() {
  return useQuery<Reward[]>({ queryKey: ['rewards'], queryFn: listRewards });
}

export function useRedeemReward() {
  const qc = useQueryClient();
  return useMutation<Redemption, unknown, string>({
    mutationFn: (rewardId: string) => redeemReward(rewardId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['me'] });
      void qc.invalidateQueries({ queryKey: ['redemptions'] });
    },
  });
}
