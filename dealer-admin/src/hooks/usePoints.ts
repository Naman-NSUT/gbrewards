import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { listPointRates, listProductRates, setPointRate } from '../api/points';
import { qk } from './keys';

/**
 * Every product with the registration points currently in force.
 *
 * Points are per product, like the worker programme's scan points. Products
 * with no rate come back with points_per_registration === null and are the rows
 * that need an admin: a dealer registering an unpriced product earns nothing.
 */
export function useProductRates() {
  return useQuery({ queryKey: qk.pointRate(), queryFn: listProductRates });
}

export function usePointRates(params: {
  product_id?: string;
  limit?: number;
  offset?: number;
}) {
  return useQuery({
    queryKey: qk.pointRates(params),
    queryFn: () => listPointRates(params),
    placeholderData: keepPreviousData,
  });
}

export function useSetPointRate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      product_id: string;
      points_per_registration: number;
      note?: string | null;
    }) => setPointRate(body),
    onSuccess: () => {
      // Only future registrations are priced by the new version — nothing
      // historic moves, so no ledger is touched.
      void qc.invalidateQueries({ queryKey: qk.points });
      void qc.invalidateQueries({ queryKey: qk.audit });
    },
  });
}
