import { useMutation, useQuery } from '@tanstack/react-query';

import { listCatalogDocs, openCatalogDoc, type CatalogDoc } from '../api/catalogDocs';

const FIVE_MINUTES = 5 * 60 * 1000;

export function useCatalogDocs() {
  return useQuery<CatalogDoc[]>({
    queryKey: ['catalog-docs'],
    queryFn: listCatalogDocs,
    staleTime: FIVE_MINUTES,
  });
}

/**
 * Downloads one sheet and hands it to a PDF viewer.
 *
 * Not cached by react-query: the result is a side effect on another app, and the
 * sheet is rendered fresh on the server each time, so there is nothing to hold.
 */
export function useOpenCatalogDoc() {
  return useMutation<void, unknown, CatalogDoc>({
    mutationFn: (doc) => openCatalogDoc(doc),
  });
}
