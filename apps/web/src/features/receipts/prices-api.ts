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
    queryFn: () => api.get<ShrinkflationSignal[]>('/receipts/analytics/shrinkflation', { fs }),
  });
}

export function useCategorySpend(params: { level?: number; fs?: FsFilter }) {
  const scope = useScope();
  return useQuery({
    queryKey: ['prices', 'category-spend', scope, params],
    queryFn: () =>
      api.get<CategorySpend[]>('/receipts/analytics/category-spend', {
        level: params.level ?? 1,
        fs: params.fs ?? 'all',
      }),
  });
}

export function useLoyalty() {
  const scope = useScope();
  return useQuery({
    queryKey: ['prices', 'loyalty', scope],
    queryFn: () => api.get<LoyaltyGroup[]>('/receipts/analytics/loyalty'),
  });
}

export function useLoyaltyReceipts(scheme: string | null, cardMasked: string | null) {
  const scope = useScope();
  return useQuery({
    queryKey: ['prices', 'loyalty-receipts', scope, scheme, cardMasked],
    queryFn: () =>
      api.get<LoyaltyAllocation[]>('/receipts/analytics/loyalty/receipts', {
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
    queryKey: ['receipts', 'link', receiptId],
    queryFn: () => api.get<ReceiptLink>(`/receipts/${receiptId}/link`),
    enabled: Boolean(receiptId),
  });
}

export function useLinkReceipt() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ receiptId, transactionId }: { receiptId: string; transactionId: string }) =>
      api.post<ReceiptLink>(`/receipts/${receiptId}/link`, { transaction_id: transactionId }),
    onSuccess: () => {
      toast.success('Fatura ligada ao movimento bancário.');
      void queryClient.invalidateQueries({ queryKey: ['receipts'] });
    },
    onError: report,
  });
}

export function useUnlinkReceipt() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (receiptId: string) => api.delete(`/receipts/${receiptId}/link`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['receipts'] });
    },
    onError: report,
  });
}

export function useSetReceiptTags() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ receiptId, tags }: { receiptId: string; tags: string[] }) =>
      api.put(`/receipts/${receiptId}/tags`, { tags }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['receipts'] });
    },
    onError: report,
  });
}
