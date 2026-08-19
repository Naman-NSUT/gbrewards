import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef } from 'react';

import { getPointsSummary, listLedger } from '../api/points';
import { listRegistrations, previewUnit } from '../api/registrations';
import { cancelRedemption, listRedemptions, listRewards, redeemReward } from '../api/rewards';
import type { UnitPreviewOut } from '../api/types';
import { useQueue } from '../offline/useQueue';

export const QUERY_KEYS = {
  registrations: ['registrations'] as const,
  points: ['points'] as const,
  ledger: ['ledger'] as const,
  rewards: ['rewards'] as const,
  redemptions: ['redemptions'] as const,
};

export function useRegistrations() {
  return useQuery({
    queryKey: QUERY_KEYS.registrations,
    queryFn: () => listRegistrations(200, 0),
  });
}

export function usePointsSummary() {
  return useQuery({ queryKey: QUERY_KEYS.points, queryFn: getPointsSummary });
}

export function useLedger() {
  return useQuery({ queryKey: QUERY_KEYS.ledger, queryFn: () => listLedger(100, 0) });
}

export function useRewards() {
  return useQuery({ queryKey: QUERY_KEYS.rewards, queryFn: listRewards });
}

export function useRedemptions() {
  return useQuery({ queryKey: QUERY_KEYS.redemptions, queryFn: listRedemptions });
}

export function useRedeemReward() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (rewardId: string) => redeemReward(rewardId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: QUERY_KEYS.points });
      void qc.invalidateQueries({ queryKey: QUERY_KEYS.redemptions });
    },
  });
}

export function useCancelRedemption() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (redemptionId: string) => cancelRedemption(redemptionId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: QUERY_KEYS.points });
      void qc.invalidateQueries({ queryKey: QUERY_KEYS.redemptions });
    },
  });
}

export function usePreviewUnit() {
  return useMutation<UnitPreviewOut, unknown, string>({
    mutationFn: (serial: string) => previewUnit(serial),
  });
}

/**
 * When the queue lands a sale, the server's copies of the registration list and
 * the point balance are stale. The queue drains from a timer with no component
 * mounted, so nothing else would ever notice.
 */
export function useQueueQuerySync(): void {
  const qc = useQueryClient();
  const { items } = useQueue();
  const seen = useRef<Set<string>>(new Set());

  useEffect(() => {
    let landed = false;
    for (const item of items) {
      if (item.status !== 'done') continue;
      if (seen.current.has(item.id)) continue;
      seen.current.add(item.id);
      landed = true;
    }
    if (landed) {
      void qc.invalidateQueries({ queryKey: QUERY_KEYS.registrations });
      void qc.invalidateQueries({ queryKey: QUERY_KEYS.points });
      void qc.invalidateQueries({ queryKey: QUERY_KEYS.ledger });
    }
  }, [items, qc]);
}
