import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  createBatch,
  createProduct,
  deleteProduct,
  getProduct,
  listProducts,
  updateProduct,
  type ProductInput,
} from '../api/products';

export function useProducts() {
  return useQuery({ queryKey: ['products'], queryFn: listProducts });
}

export function useProduct(id: string | null) {
  return useQuery({
    queryKey: ['product', id],
    queryFn: () => getProduct(id as string),
    enabled: id !== null,
  });
}

export function useCreateProduct() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: ProductInput) => createProduct(input),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['products'] }),
  });
}

export function useUpdateProduct() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: Partial<ProductInput> }) =>
      updateProduct(id, input),
    onSuccess: (_d, { id }) => {
      void qc.invalidateQueries({ queryKey: ['products'] });
      void qc.invalidateQueries({ queryKey: ['product', id] });
    },
  });
}

export function useDeleteProduct() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteProduct(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['products'] }),
  });
}

export function useCreateBatch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ productId, quantity, label }: { productId: string; quantity: number; label?: string }) =>
      createBatch(productId, quantity, label),
    onSuccess: (_d, { productId }) => {
      void qc.invalidateQueries({ queryKey: ['product', productId] });
    },
  });
}
