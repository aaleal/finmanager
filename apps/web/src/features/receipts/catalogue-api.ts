import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { api, ApiError } from '@/lib/api';
import type {
  CategoryImpact,
  CategoryOperationResult,
  CategoryResult,
  CategoryTreeNode,
  LegacyImportResult,
  MasterProduct,
  Merchant,
  MergeCandidate,
  Page,
  ProductAlias,
  ProductOccurrence,
  ProductSearchResult,
} from '@/lib/types';

export type ProductFilters = {
  search?: string;
  category_id?: string;
  category_status?: string;
  page?: string;
  page_size?: string;
};

function report(error: unknown) {
  toast.error(error instanceof ApiError ? error.message : 'Ocorreu um erro inesperado.');
}

/** The catalogue is household reference data, so its keys carry no entity. */
function useInvalidate() {
  const queryClient = useQueryClient();
  return () => {
    void queryClient.invalidateQueries({ queryKey: ['products'] });
    void queryClient.invalidateQueries({ queryKey: ['categories'] });
    void queryClient.invalidateQueries({ queryKey: ['receipts'] });
    void queryClient.invalidateQueries({ queryKey: ['receipt-items'] });
  };
}

export function useProducts(filters: ProductFilters) {
  return useQuery({
    queryKey: ['products', 'list', filters],
    queryFn: () =>
      api.get<Page<MasterProduct>>('/master-products', {
        search: filters.search,
        category_id: filters.category_id,
        category_status: filters.category_status,
        page: filters.page ?? '1',
        page_size: filters.page_size ?? '50',
      }),
    placeholderData: (previous) => previous,
  });
}

export function useProduct(productId: string | null) {
  return useQuery({
    queryKey: ['products', 'detail', productId],
    queryFn: () => api.get<MasterProduct>(`/master-products/${productId}`),
    enabled: Boolean(productId),
  });
}

export function useProductAliases(productId: string | null) {
  return useQuery({
    queryKey: ['products', 'aliases', productId],
    queryFn: () => api.get<ProductAlias[]>(`/master-products/${productId}/aliases`),
    enabled: Boolean(productId),
  });
}

export function useMerchants() {
  return useQuery({
    queryKey: ['merchants'],
    queryFn: () => api.get<Merchant[]>('/merchants'),
    staleTime: 60_000,
  });
}

/**
 * Teach the catalogue a merchant's wording by hand.
 *
 * The same call the review pane makes when a product is corrected, so a
 * hand-written alias is indistinguishable from a learned one and rises through
 * the same confidence.
 */
export function useLearnAlias() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: {
      master_product_id: string;
      merchant_id: string;
      merchant_description: string;
    }) => api.post<ProductAlias>('/product-aliases/learn', body),
    onSuccess: () => {
      toast.success('Alias aprendido. A próxima linha com este texto resolve sozinha.');
      invalidate();
    },
    onError: report,
  });
}

export function useProductOccurrences(productId: string | null) {
  return useQuery({
    queryKey: ['products', 'occurrences', productId],
    queryFn: () => api.get<ProductOccurrence[]>(`/master-products/${productId}/occurrences`),
    enabled: Boolean(productId),
  });
}

/** Autocomplete over canonical names, brands and learned aliases. */
export function useProductSearch(query: string, enabled = true) {
  return useQuery({
    queryKey: ['products', 'search', query],
    queryFn: () => api.get<ProductSearchResult[]>('/master-products/search', { q: query }),
    enabled: enabled && query.trim().length >= 2,
    staleTime: 30_000,
  });
}

export function useMergeCandidates() {
  return useQuery({
    queryKey: ['products', 'merge-candidates'],
    queryFn: () => api.get<MergeCandidate[]>('/master-products/merge-candidates'),
  });
}

export function useCategorySearch(query: string) {
  return useQuery({
    queryKey: ['categories', 'search', query],
    queryFn: () =>
      api.get<CategoryResult[]>('/categories/search', { q: query, domain: 'GROCERY', limit: 40 }),
    staleTime: 60_000,
  });
}

/** The whole tree, uncapped — the editor must never mistake a cut-off node for a retired one. */
export function useCategoryTree() {
  return useQuery({
    queryKey: ['categories', 'tree'],
    queryFn: () => api.get<CategoryTreeNode[]>('/categories/tree', { domain: 'GROCERY' }),
    staleTime: 60_000,
  });
}

/** How many rows a destructive operation would touch, **before** it runs. */
export function useCategoryImpact(categoryId: string | null) {
  return useQuery({
    queryKey: ['categories', 'impact', categoryId],
    queryFn: () => api.get<CategoryImpact>(`/categories/${categoryId}/impact`),
    enabled: Boolean(categoryId),
  });
}

export function useCreateProduct() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post<MasterProduct>('/master-products', body),
    onSuccess: () => {
      toast.success('Produto criado.');
      invalidate();
    },
    onError: report,
  });
}

export function useUpdateProduct() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ productId, patch }: { productId: string; patch: Record<string, unknown> }) =>
      api.patch<MasterProduct>(`/master-products/${productId}`, patch),
    onSuccess: () => {
      toast.success('Produto atualizado.');
      invalidate();
    },
    onError: report,
  });
}

/** Idempotent on the weight, so appending a format never has to send the others. */
export function useAddPackVariant() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ productId, weightKg }: { productId: string; weightKg: string }) =>
      api.post<MasterProduct>(`/master-products/${productId}/pack-variants`, {
        weight_kg: weightKg,
      }),
    onSuccess: () => {
      toast.success('Formato adicionado ao produto.');
      invalidate();
    },
    onError: report,
  });
}

export function useValidateProductCategory() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (productId: string) =>
      api.post<MasterProduct>(`/master-products/${productId}/validate-category`),
    onSuccess: () => {
      toast.success('Categoria confirmada para todas as linhas deste produto.');
      invalidate();
    },
    onError: report,
  });
}

export function useMergeProducts() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ targetId, sourceId }: { targetId: string; sourceId: string }) =>
      api.post<MasterProduct>(`/master-products/${targetId}/merge`, { source_id: sourceId }),
    onSuccess: () => {
      toast.success('Produtos fundidos.');
      invalidate();
    },
    onError: report,
  });
}

export function useReassignItemProduct() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ itemId, masterProductId }: { itemId: string; masterProductId: string }) =>
      api.patch(`/receipt-items/${itemId}/product`, { master_product_id: masterProductId }),
    onSuccess: () => {
      toast.success('Produto corrigido. A correção fica aprendida para este comerciante.');
      invalidate();
    },
    onError: report,
  });
}

export function useConfirmReceiptCategories() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (receiptId: string) => api.post(`/receipts/${receiptId}/confirm-categories`),
    onSuccess: () => {
      toast.success('Categorias confirmadas.');
      invalidate();
    },
    onError: report,
  });
}

export function useCreateCategory() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: { display_name_pt: string; parent_id?: string | null }) =>
      api.post<CategoryResult>('/categories', body),
    onSuccess: () => {
      toast.success('Categoria criada.');
      invalidate();
    },
    onError: report,
  });
}

export function useRenameCategory() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ categoryId, name }: { categoryId: string; name: string }) =>
      api.patch<CategoryResult>(`/categories/${categoryId}`, { display_name_pt: name }),
    onSuccess: () => invalidate(),
    onError: report,
  });
}

export function useReparentCategory() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ categoryId, parentId }: { categoryId: string; parentId: string | null }) =>
      api.post<CategoryOperationResult>(`/categories/${categoryId}/reparent`, {
        parent_id: parentId,
      }),
    onSuccess: (result) => {
      toast.success(result.message ?? 'Categoria movida.');
      invalidate();
    },
    onError: report,
  });
}

export function useMergeCategories() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ categoryId, targetId }: { categoryId: string; targetId: string }) =>
      api.post<CategoryOperationResult>(`/categories/${categoryId}/merge`, { target_id: targetId }),
    onSuccess: (result) => {
      toast.success(result.message ?? 'Categorias fundidas.');
      invalidate();
    },
    onError: report,
  });
}

export function useRetireCategory() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (categoryId: string) => api.delete(`/categories/${categoryId}`),
    onSuccess: () => {
      toast.success('Categoria retirada.');
      invalidate();
    },
    onError: report,
  });
}

export function useLegacyImport() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append('file', file);
      return api.upload<LegacyImportResult>('/receipts/import/legacy', form, undefined, 'POST');
    },
    onSuccess: (result) => {
      toast.success(
        `${result.receipts_created} fatura(s) importadas · ${result.products_created} produtos criados.`,
      );
      invalidate();
    },
    onError: report,
  });
}
