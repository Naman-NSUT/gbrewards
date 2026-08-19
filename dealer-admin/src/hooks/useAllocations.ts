import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  listAllocationBatches,
  listAllocations,
  previewAllocationCsv,
  revokeAllocation,
  uploadAllocationCsv,
  type AllocationsQuery,
} from '../api/allocations';
import { qk } from './keys';

export function useAllocations(params: AllocationsQuery) {
  return useQuery({
    queryKey: qk.allocationList(params),
    queryFn: () => listAllocations(params),
    placeholderData: keepPreviousData,
  });
}

export function useAllocationBatches(params: { limit?: number; offset?: number }) {
  return useQuery({
    queryKey: qk.allocationBatches(params),
    queryFn: () => listAllocationBatches(params),
    placeholderData: keepPreviousData,
  });
}

/** Dry run — deliberately NOT invalidating anything, because it writes nothing. */
export function usePreviewAllocationCsv() {
  return useMutation({ mutationFn: (file: File) => previewAllocationCsv(file) });
}

export function useUploadAllocationCsv() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => uploadAllocationCsv(file),
    onSuccess: () => {
      // Allocation is the denominator of the compliance metric, so an upload
      // moves every dealer's rate the moment it lands.
      void qc.invalidateQueries({ queryKey: qk.allocations });
      void qc.invalidateQueries({ queryKey: qk.compliance });
      void qc.invalidateQueries({ queryKey: qk.dealers });
      void qc.invalidateQueries({ queryKey: qk.dashboard });
      void qc.invalidateQueries({ queryKey: qk.audit });
    },
  });
}

export function useRevokeAllocation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => revokeAllocation(id, { reason }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: qk.allocations });
      void qc.invalidateQueries({ queryKey: qk.compliance });
      void qc.invalidateQueries({ queryKey: qk.dealers });
      void qc.invalidateQueries({ queryKey: qk.audit });
      void qc.invalidateQueries({ queryKey: qk.lookup });
    },
  });
}
