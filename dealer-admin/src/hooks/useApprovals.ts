import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  approveWarranty,
  getApprovalCounts,
  listApprovals,
  rejectWarranty,
  type ApprovalsQuery,
} from '../api/approvals';
import { qk } from './keys';

export function useApprovals(params: ApprovalsQuery) {
  return useQuery({
    queryKey: qk.approvalsList(params),
    queryFn: () => listApprovals(params),
    placeholderData: keepPreviousData,
  });
}

/** Counts come from /admin/approvals/count — the list response has no totals
 *  broken down by status, only its own `total`. */
export function useApprovalCounts() {
  return useQuery({ queryKey: qk.approvalCounts(), queryFn: getApprovalCounts });
}

/**
 * A decision here activates a warranty and may credit points, so it moves the
 * queue, the dealer's compliance rate, the ledger and the audit trail at once.
 */
function useApprovalInvalidation() {
  const qc = useQueryClient();
  return () => {
    void qc.invalidateQueries({ queryKey: qk.approvals });
    void qc.invalidateQueries({ queryKey: qk.warranties });
    void qc.invalidateQueries({ queryKey: qk.dashboard });
    void qc.invalidateQueries({ queryKey: qk.compliance });
    void qc.invalidateQueries({ queryKey: qk.dealers });
    void qc.invalidateQueries({ queryKey: qk.audit });
    void qc.invalidateQueries({ queryKey: qk.lookup });
  };
}

export function useApproveWarranty() {
  const invalidate = useApprovalInvalidation();
  return useMutation({
    mutationFn: ({
      id,
      reason,
      honourRequestedDate,
    }: {
      id: string;
      reason: string;
      honourRequestedDate: boolean;
    }) => approveWarranty(id, { reason, honour_requested_date: honourRequestedDate }),
    onSuccess: invalidate,
  });
}

export function useRejectWarranty() {
  const invalidate = useApprovalInvalidation();
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => rejectWarranty(id, { reason }),
    onSuccess: invalidate,
  });
}
