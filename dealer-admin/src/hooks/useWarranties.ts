import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  getWarranty,
  listWarranties,
  updateWarrantyCustomer,
  voidWarranty,
  type CustomerPatch,
  type WarrantiesQuery,
} from '../api/warranties';
import { qk } from './keys';

export function useWarranties(params: WarrantiesQuery) {
  return useQuery({
    queryKey: qk.warrantyList(params),
    queryFn: () => listWarranties(params),
    placeholderData: keepPreviousData,
  });
}

export function useWarranty(id: string | null) {
  return useQuery({
    queryKey: qk.warrantyDetail(id),
    queryFn: () => getWarranty(id as string),
    enabled: id !== null,
  });
}

export function useVoidWarranty() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason, clawback }: { id: string; reason: string; clawback: boolean }) =>
      voidWarranty(id, { reason, clawback }),
    onSuccess: (_data, { id }) => {
      // A void writes a compensating debit and frees the allocation, so points,
      // compliance and the serial's own record all move with it.
      void qc.invalidateQueries({ queryKey: qk.warranties });
      void qc.invalidateQueries({ queryKey: qk.warrantyDetail(id) });
      void qc.invalidateQueries({ queryKey: qk.dashboard });
      void qc.invalidateQueries({ queryKey: qk.compliance });
      void qc.invalidateQueries({ queryKey: qk.allocations });
      void qc.invalidateQueries({ queryKey: qk.points });
      void qc.invalidateQueries({ queryKey: qk.dealers });
      void qc.invalidateQueries({ queryKey: qk.audit });
      void qc.invalidateQueries({ queryKey: qk.lookup });
    },
  });
}

export function useUpdateWarrantyCustomer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: CustomerPatch }) =>
      updateWarrantyCustomer(id, patch),
    onSuccess: (_data, { id }) => {
      void qc.invalidateQueries({ queryKey: qk.warrantyDetail(id) });
      void qc.invalidateQueries({ queryKey: qk.warranties });
      void qc.invalidateQueries({ queryKey: qk.audit });
      void qc.invalidateQueries({ queryKey: qk.lookup });
    },
  });
}
