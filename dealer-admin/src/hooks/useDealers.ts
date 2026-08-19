import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  adjustDealerPoints,
  createDealer,
  createDealerStaff,
  getDealer,
  getDealerLedger,
  getDealerPoints,
  listDealerStaff,
  listDealers,
  reactivateDealer,
  suspendDealer,
  updateDealer,
  updateDealerStaff,
  type DealersQuery,
} from '../api/dealers';
import type { DealerInput, StaffInput } from '../api/types';
import { qk } from './keys';

export function useDealers(params: DealersQuery) {
  return useQuery({
    queryKey: qk.dealerList(params),
    queryFn: () => listDealers(params),
    placeholderData: keepPreviousData,
  });
}

export function useDealer(id: string | null) {
  return useQuery({
    queryKey: qk.dealerDetail(id),
    queryFn: () => getDealer(id as string),
    enabled: id !== null,
  });
}

export function useDealerStaff(dealerId: string | null) {
  return useQuery({
    queryKey: qk.dealerStaff(dealerId),
    queryFn: () => listDealerStaff(dealerId as string, { include_inactive: true }),
    enabled: dealerId !== null,
  });
}

export function useDealerPoints(dealerId: string | null) {
  return useQuery({
    queryKey: qk.dealerPoints(dealerId),
    queryFn: () => getDealerPoints(dealerId as string),
    enabled: dealerId !== null,
  });
}

export function useDealerLedger(
  dealerId: string | null,
  params: { limit?: number; offset?: number },
) {
  return useQuery({
    queryKey: qk.dealerLedger(dealerId, params),
    queryFn: () => getDealerLedger(dealerId as string, params),
    enabled: dealerId !== null,
    placeholderData: keepPreviousData,
  });
}

export function useCreateDealer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: DealerInput) => createDealer(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: qk.dealers });
      void qc.invalidateQueries({ queryKey: qk.compliance });
      void qc.invalidateQueries({ queryKey: qk.dashboard });
      void qc.invalidateQueries({ queryKey: qk.audit });
    },
  });
}

export function useUpdateDealer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<DealerInput> }) =>
      updateDealer(id, body),
    onSuccess: (_d, { id }) => {
      void qc.invalidateQueries({ queryKey: qk.dealers });
      void qc.invalidateQueries({ queryKey: qk.dealerDetail(id) });
      void qc.invalidateQueries({ queryKey: qk.compliance });
      void qc.invalidateQueries({ queryKey: qk.audit });
    },
  });
}

export function useSuspendDealer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => suspendDealer(id, { reason }),
    onSuccess: (_d, { id }) => {
      void qc.invalidateQueries({ queryKey: qk.dealers });
      void qc.invalidateQueries({ queryKey: qk.dealerDetail(id) });
      void qc.invalidateQueries({ queryKey: qk.compliance });
      void qc.invalidateQueries({ queryKey: qk.dashboard });
      void qc.invalidateQueries({ queryKey: qk.audit });
    },
  });
}

export function useReactivateDealer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => reactivateDealer(id),
    onSuccess: (_d, id) => {
      void qc.invalidateQueries({ queryKey: qk.dealers });
      void qc.invalidateQueries({ queryKey: qk.dealerDetail(id) });
      void qc.invalidateQueries({ queryKey: qk.compliance });
      void qc.invalidateQueries({ queryKey: qk.dashboard });
      void qc.invalidateQueries({ queryKey: qk.audit });
    },
  });
}

export function useCreateDealerStaff() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ dealerId, body }: { dealerId: string; body: StaffInput }) =>
      createDealerStaff(dealerId, body),
    onSuccess: (_d, { dealerId }) => {
      void qc.invalidateQueries({ queryKey: qk.dealerStaff(dealerId) });
      void qc.invalidateQueries({ queryKey: qk.dealerDetail(dealerId) });
      void qc.invalidateQueries({ queryKey: qk.dealers });
      void qc.invalidateQueries({ queryKey: qk.audit });
    },
  });
}

export function useUpdateDealerStaff() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      dealerId,
      staffId,
      body,
    }: {
      dealerId: string;
      staffId: string;
      body: { name?: string | null; role?: string | null; is_active?: boolean | null };
    }) => updateDealerStaff(dealerId, staffId, body),
    onSuccess: (_d, { dealerId }) => {
      void qc.invalidateQueries({ queryKey: qk.dealerStaff(dealerId) });
      void qc.invalidateQueries({ queryKey: qk.dealerDetail(dealerId) });
      void qc.invalidateQueries({ queryKey: qk.dealers });
      void qc.invalidateQueries({ queryKey: qk.audit });
    },
  });
}

/** The adjustment endpoint hangs off the dealer, so this lives here, not in
 *  usePoints — there is no global /admin/points/adjust. */
export function useAdjustDealerPoints() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      dealerId,
      amount,
      reason,
    }: {
      dealerId: string;
      amount: number;
      reason: string;
    }) => adjustDealerPoints(dealerId, { amount, reason }),
    onSuccess: () => {
      // Every dealers-scoped key (detail, ledger, points) hangs off qk.dealers,
      // and a balance change is visible on all three.
      void qc.invalidateQueries({ queryKey: qk.dealers });
      void qc.invalidateQueries({ queryKey: qk.points });
      void qc.invalidateQueries({ queryKey: qk.dashboard });
      void qc.invalidateQueries({ queryKey: qk.audit });
    },
  });
}
