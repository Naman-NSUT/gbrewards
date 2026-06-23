import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  creditUser,
  debitUser,
  getUser,
  getUserLedger,
  listUsers,
  setUserActive,
} from '../api/users';

export function useUsers(q: string, cursor?: string) {
  return useQuery({
    queryKey: ['users', q, cursor ?? null],
    queryFn: () => listUsers({ q: q || undefined, cursor }),
  });
}

export function useUser(id: string | null) {
  return useQuery({
    queryKey: ['user', id],
    queryFn: () => getUser(id as string),
    enabled: id !== null,
  });
}

export function useUserLedger(id: string | null, cursor?: string) {
  return useQuery({
    queryKey: ['user-ledger', id, cursor ?? null],
    queryFn: () => getUserLedger(id as string, { cursor }),
    enabled: id !== null,
  });
}

function useUserMutation<TArgs>(fn: (args: TArgs) => Promise<unknown>, userId: () => string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      const id = userId();
      void qc.invalidateQueries({ queryKey: ['users'] });
      void qc.invalidateQueries({ queryKey: ['user', id] });
      void qc.invalidateQueries({ queryKey: ['user-ledger', id] });
    },
  });
}

export function useCreditUser(id: string | null) {
  return useUserMutation(
    ({ points, note }: { points: number; note?: string }) => creditUser(id as string, points, note),
    () => id,
  );
}

export function useDebitUser(id: string | null) {
  return useUserMutation(
    ({ points, note }: { points: number; note?: string }) => debitUser(id as string, points, note),
    () => id,
  );
}

export function useSetUserActive() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, isActive }: { id: string; isActive: boolean }) => setUserActive(id, isActive),
    onSuccess: (_d, { id }) => {
      void qc.invalidateQueries({ queryKey: ['users'] });
      void qc.invalidateQueries({ queryKey: ['user', id] });
    },
  });
}
