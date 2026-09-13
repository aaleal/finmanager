import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { api, ApiError, download } from '@/lib/api';
import { useSession } from '@/features/auth/session';
import type {
  CategorySpend,
  FsFilter,
  LoyaltyAllocation,
  LoyaltyGroup,
  PriceHistory,
  ReceiptLink,
  ShrinkflationSignal,
} from '@/lib/types';

function useScope() {
  const { session } = useSession();
  return session?.active_entity_id ?? 'all';
}

function report(error: unknown) {
  toast.error(error instanceof ApiError ? error.message : 'Ocorreu um erro inesperado.');
}

export function usePriceHistory(productId: string | null, fs: FsFilter = 'all') {
  const scope = useScope();
  return useQuery({
    queryKey: ['prices', 'history', scope, productId, fs],
    queryFn: () => api.get<PriceHistory>(`/master-products/${productId}/price-history`, { fs }),
    enabled: Boolean(productId),
  });
}

export function useShrinkflation(fs: FsFilter = 'all') {
  const scope = useScope();
  return useQuery({
    queryKey: ['prices', 'shrinkflation', scope, fs],
    queryFn: () => api.get<ShrinkflationSignal[]>('/supermarket/analytics/shrinkflation', { fs }),
  });
}

export type SpendDimension = 'category' | 'brand' | 'own_brand' | 'conservation' | 'presentation';

export type SpendFilters = {
  level?: number;
  dimension?: SpendDimension;
  fs?: FsFilter;
  is_own_brand?: boolean;
  brand?: string;
  conservation?: string;
  presentation?: string;
  dietary?: string[];
};

export function useCategorySpend(params: SpendFilters) {
  const scope = useScope();
  return useQuery({
    queryKey: ['prices', 'category-spend', scope, params],
    queryFn: () =>
      api.get<CategorySpend[]>('/supermarket/analytics/category-spend', {
        level: params.level ?? 1,
        dimension: params.dimension ?? 'category',
        fs: params.fs ?? 'all',
        is_own_brand: params.is_own_brand,
        brand: params.brand,
        conservation: params.conservation,
        presentation: params.presentation,
        dietary: params.dietary,
      }),
  });
}

/** Its own endpoint because the rows deliberately do not sum to total spend: a
 * product carrying two tags is counted under both. */
export function useDietarySpend(params: { fs?: FsFilter } = {}) {
  const scope = useScope();
  return useQuery({
    queryKey: ['prices', 'dietary-spend', scope, params],
    queryFn: () =>
      api.get<CategorySpend[]>('/supermarket/analytics/dietary-spend', {
        fs: params.fs ?? 'all',
      }),
  });
}

export function useLoyalty() {
  const scope = useScope();
  return useQuery({
    queryKey: ['prices', 'loyalty', scope],
    queryFn: () => api.get<LoyaltyGroup[]>('/supermarket/analytics/loyalty'),
  });
}

export function useLoyaltyReceipts(scheme: string | null, cardMasked: string | null) {
  const scope = useScope();
  return useQuery({
    queryKey: ['prices', 'loyalty-receipts', scope, scheme, cardMasked],
    queryFn: () =>
      api.get<LoyaltyAllocation[]>('/supermarket/analytics/loyalty/receipts', {
        scheme: scheme ?? undefined,
        card_masked: cardMasked ?? undefined,
      }),
    enabled: Boolean(scheme),
  });
}

export function useExportPriceHistory() {
  return useMutation({
    mutationFn: ({ productId, fs }: { productId: string; fs: FsFilter }) =>
      download(`/master-products/${productId}/price-history.csv`, { fs }),
    onError: report,
  });
}

/** Answers `ledger_available: false` until the Banking module lands (ADR-0005). */
export function useReceiptLink(receiptId: string | null) {
  return useQuery({
    queryKey: ['supermarket', 'link', receiptId],
    queryFn: () => api.get<ReceiptLink>(`/supermarket/${receiptId}/link`),
    enabled: Boolean(receiptId),
  });
}

export function useLinkReceipt() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ receiptId, transactionId }: { receiptId: string; transactionId: string }) =>
      api.post<ReceiptLink>(`/supermarket/${receiptId}/link`, { transaction_id: transactionId }),
    onSuccess: () => {
      toast.success('Fatura ligada ao movimento bancário.');
      void queryClient.invalidateQueries({ queryKey: ['supermarket'] });
    },
    onError: report,
  });
}

export function useUnlinkReceipt() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (receiptId: string) => api.delete(`/supermarket/${receiptId}/link`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['supermarket'] });
    },
    onError: report,
  });
}

export function useSetReceiptTags() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ receiptId, tags }: { receiptId: string; tags: string[] }) =>
      api.put(`/supermarket/${receiptId}/tags`, { tags }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['supermarket'] });
    },
    onError: report,
  });
}
