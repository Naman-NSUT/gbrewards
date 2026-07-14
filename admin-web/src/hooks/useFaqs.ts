import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { createFaq, deleteFaq, listFaqs, updateFaq } from '../api/faqs';
import type { FaqInput } from '../api/types';

export function useFaqs() {
  return useQuery({ queryKey: ['faqs'], queryFn: listFaqs });
}

export function useCreateFaq() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: FaqInput) => createFaq(input),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['faqs'] }),
  });
}

export function useUpdateFaq() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: Partial<FaqInput> }) => updateFaq(id, input),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['faqs'] }),
  });
}

export function useDeleteFaq() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteFaq(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['faqs'] }),
  });
}
