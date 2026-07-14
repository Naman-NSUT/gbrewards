import { useQuery } from '@tanstack/react-query';

import {
  getContent,
  listFaqs,
  listProductPoints,
  type ContentDoc,
  type Faq,
  type ProductPoints,
} from '../api/content';

const FIVE_MINUTES = 5 * 60 * 1000;

export function useProductPoints() {
  return useQuery<ProductPoints[]>({
    queryKey: ['product-points'],
    queryFn: listProductPoints,
    staleTime: FIVE_MINUTES,
  });
}

export function useFaqs() {
  return useQuery<Faq[]>({
    queryKey: ['faqs'],
    queryFn: listFaqs,
    staleTime: FIVE_MINUTES,
  });
}

export function useTerms() {
  return useQuery<ContentDoc>({
    queryKey: ['content', 'terms'],
    queryFn: () => getContent('terms'),
    staleTime: FIVE_MINUTES,
  });
}
