import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { listRewards, type Reward } from '../api/rewards';
import { redeemReward } from '../api/redemptions';
import type { Redemption } from '../api/types';

export function useRewards() {
  return useQuery<Reward[]>({ queryKey: ['rewards'], queryFn: listRewards });
}

export interface RedeemVars {
  rewardId: string;
  quantity: number;
}

export function useRedeemReward() {
  const qc = useQueryClient();
  return useMutation<Redemption, unknown, RedeemVars>({
    mutationFn: ({ rewardId, quantity }) => redeemReward(rewardId, quantity),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['me'] });
      void qc.invalidateQueries({ queryKey: ['redemptions'] });
    },
  });
}
