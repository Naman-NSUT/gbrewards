import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  approveRedemption,
  listRedemptions,
  markRedemptionFulfilled,
  rejectRedemption,
  type RedemptionsQuery,
} from '../api/redemptions';
import { qk } from './keys';

export function useRedemptions(params: RedemptionsQuery) {
  return useQuery({
    queryKey: qk.redemptionList(params),
    queryFn: () => listRedemptions(params),
    placeholderData: keepPreviousData,
  });
}

// TResult is threaded through so callers keep the decision payload — the
// balance after the debit is the one number the approver actually needs back.
function useRedemptionMutation<TArgs, TResult>(fn: (args: TArgs) => Promise<TResult>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      // Approval writes the redemption_debit; rejection releases the pending
      // hold. Either way every balance on screen has moved.
      void qc.invalidateQueries({ queryKey: qk.redemptions });
      void qc.invalidateQueries({ queryKey: qk.points });
      void qc.invalidateQueries({ queryKey: qk.dealers });
      void qc.invalidateQueries({ queryKey: qk.dashboard });
      void qc.invalidateQueries({ queryKey: qk.audit });
    },
  });
}

export function useApproveRedemption() {
  return useRedemptionMutation(({ id, note }: { id: string; note?: string | null }) =>
    approveRedemption(id, { note }),
  );
}

export function useRejectRedemption() {
  return useRedemptionMutation(({ id, reason }: { id: string; reason: string }) =>
    rejectRedemption(id, { reason }),
  );
}

export function useMarkRedemptionFulfilled() {
  return useRedemptionMutation(({ id, note }: { id: string; note?: string | null }) =>
    markRedemptionFulfilled(id, { note }),
  );
}
