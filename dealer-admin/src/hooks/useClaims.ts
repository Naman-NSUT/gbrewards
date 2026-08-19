import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { getClaim, listClaims, updateClaim, type ClaimsQuery } from '../api/claims';
import type { ClaimStatus } from '../api/types';
import { qk } from './keys';

export function useClaims(params: ClaimsQuery) {
  return useQuery({
    queryKey: qk.claimList(params),
    queryFn: () => listClaims(params),
    placeholderData: keepPreviousData,
  });
}

/** The list row carries no resolution note — the detail endpoint does. */
export function useClaim(id: string | null) {
  return useQuery({
    queryKey: qk.claimDetail(id),
    queryFn: () => getClaim(id as string),
    enabled: id !== null,
  });
}

export function useUpdateClaim() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      status,
      resolutionNote,
    }: {
      id: string;
      status: ClaimStatus;
      resolutionNote?: string | null;
    }) => updateClaim(id, { status, resolution_note: resolutionNote }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: qk.claims });
      void qc.invalidateQueries({ queryKey: qk.dashboard });
      void qc.invalidateQueries({ queryKey: qk.lookup });
      void qc.invalidateQueries({ queryKey: qk.audit });
    },
  });
}
