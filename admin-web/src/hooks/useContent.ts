import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { getContentDoc, listContentDocs, upsertContentDoc } from '../api/content';
import type { ContentDocInput } from '../api/types';

export function useContentDocs() {
  return useQuery({ queryKey: ['content'], queryFn: listContentDocs });
}

export function useContentDoc(key: string | null) {
  return useQuery({
    queryKey: ['content', key],
    queryFn: () => getContentDoc(key as string),
    enabled: key !== null,
  });
}

export function useUpsertContentDoc() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ key, input }: { key: string; input: ContentDocInput }) =>
      upsertContentDoc(key, input),
    onSuccess: (_d, { key }) => {
      void qc.invalidateQueries({ queryKey: ['content'] });
      void qc.invalidateQueries({ queryKey: ['content', key] });
    },
  });
}
