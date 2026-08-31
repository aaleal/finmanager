import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { api, ApiError } from '@/lib/api';
import { useSession } from '@/features/auth/session';
import type {
  FsFilter,
  Page,
  ParserOption,
  ParserProfile,
  ProductSummary,
  QueueEntry,
  ReceiptDetail,
  ReceiptItem,
  ReceiptStatusBoard,
  ReceiptSummary,
  UploadResponse,
} from '@/lib/types';

/** Every receipt query key carries the active entity so switching invalidates cleanly. */
function useScope() {
  const { session } = useSession();
  return session?.active_entity_id ?? 'all';
}

export type ReceiptFilters = {
  search?: string;
  merchant_id?: string;
  status?: string;
  date_from?: string;
  date_to?: string;
  fs?: FsFilter;
  page?: string;
  page_size?: string;
};

export type ItemFilters = {
  search?: string;
  merchant_id?: string;
  date_from?: string;
  date_to?: string;
  fs?: FsFilter;
  product_flag?: string;
  master_product_id?: string;
  page?: string;
  page_size?: string;
};

export function useReceiptStatusBoard() {
  const scope = useScope();
  return useQuery({
    queryKey: ['receipts', 'status', scope],
    queryFn: () => api.get<ReceiptStatusBoard>('/receipts/status'),
    refetchInterval: 30_000,
  });
}

export function useReceiptQueue() {
  const scope = useScope();
  return useQuery({
    queryKey: ['receipts', 'queue', scope],
    queryFn: () => api.get<QueueEntry[]>('/receipts/queue'),
  });
}

export function useReceipts(filters: ReceiptFilters) {
  const scope = useScope();
  return useQuery({
    queryKey: ['receipts', 'list', scope, filters],
    queryFn: () =>
      api.get<Page<ReceiptSummary>>('/receipts', {
        search: filters.search,
        merchant_id: filters.merchant_id,
        status: filters.status,
        date_from: filters.date_from,
        date_to: filters.date_to,
        fs: filters.fs ?? 'all',
        page: filters.page ?? '1',
        page_size: filters.page_size ?? '25',
      }),
    placeholderData: (previous) => previous,
  });
}

export function useReceipt(receiptId: string | null) {
  return useQuery({
    queryKey: ['receipts', 'detail', receiptId],
    queryFn: () => api.get<ReceiptDetail>(`/receipts/${receiptId}`),
    enabled: Boolean(receiptId),
  });
}

export function useReceiptItems(filters: ItemFilters) {
  const scope = useScope();
  return useQuery({
    queryKey: ['receipt-items', scope, filters],
    queryFn: () =>
      api.get<Page<ReceiptItem>>('/receipt-items', {
        search: filters.search,
        merchant_id: filters.merchant_id,
        date_from: filters.date_from,
        date_to: filters.date_to,
        fs: filters.fs ?? 'all',
        product_flag: filters.product_flag,
        master_product_id: filters.master_product_id,
        page: filters.page ?? '1',
        page_size: filters.page_size ?? '50',
      }),
    placeholderData: (previous) => previous,
  });
}

/** The same lines, grouped: one row per product instead of one per purchase. */
export function useProductSummary(filters: ItemFilters, enabled = true) {
  const scope = useScope();
  return useQuery({
    queryKey: ['receipt-items', 'summary', scope, filters],
    queryFn: () =>
      api.get<Page<ProductSummary>>('/receipt-items/summary', {
        search: filters.search,
        merchant_id: filters.merchant_id,
        date_from: filters.date_from,
        date_to: filters.date_to,
        fs: filters.fs ?? 'all',
        product_flag: filters.product_flag,
        page: filters.page ?? '1',
        page_size: filters.page_size ?? '50',
      }),
    enabled,
    placeholderData: (previous) => previous,
  });
}

export function useParserProfiles() {
  return useQuery({
    queryKey: ['receipts', 'parser-profiles'],
    queryFn: () => api.get<ParserProfile[]>('/parser-profiles'),
  });
}

export function useParserOptions() {
  return useQuery({
    queryKey: ['receipts', 'parsers'],
    queryFn: () => api.get<ParserOption[]>('/parser-profiles/parsers'),
    staleTime: Infinity,
  });
}

/** Invalidate the item, the queue, the list and the status board — never a partial. */
function useInvalidate() {
  const queryClient = useQueryClient();
  return (receiptId?: string) => {
    void queryClient.invalidateQueries({ queryKey: ['receipts'] });
    void queryClient.invalidateQueries({ queryKey: ['receipt-items'] });
    void queryClient.invalidateQueries({ queryKey: ['review'] });
    if (receiptId) {
      void queryClient.invalidateQueries({ queryKey: ['receipts', 'detail', receiptId] });
    }
  };
}

function report(error: unknown) {
  toast.error(error instanceof ApiError ? error.message : 'Ocorreu um erro inesperado.');
}

export function useUploadReceipts() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ files, parserProfileId }: { files: File[]; parserProfileId?: string }) => {
      const form = new FormData();
      files.forEach((file) => form.append('files', file));
      // Forcing a profile is the escape hatch for a layout detection missed; the
      // profile that ran is recorded on the receipt either way (UX-1.1).
      return api.upload<UploadResponse>(
        '/receipts',
        form,
        parserProfileId ? { parser_profile_id: parserProfileId } : undefined,
        'POST',
      );
    },
    onSuccess: (result) => {
      const created = result.items.filter((item) => item.created).length;
      const repeated = result.items.length - created;
      if (created) toast.success(`${created} fatura(s) em processamento.`);
      if (repeated) toast.info(`${repeated} fatura(s) já existiam e foram ignoradas.`);
      invalidate();
    },
    onError: report,
  });
}

export function useReparse() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ receiptId, profileId }: { receiptId: string; profileId?: string }) =>
      api.post<ReceiptDetail>(
        `/receipts/${receiptId}/reparse`,
        undefined,
        profileId ? { parser_profile_id: profileId } : undefined,
      ),
    onSuccess: (receipt) => {
      toast.success('Fatura reprocessada.');
      invalidate(receipt.id);
    },
    onError: report,
  });
}

export function useConfirmReceipt() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (receiptId: string) => api.post<ReceiptDetail>(`/receipts/${receiptId}/confirm`),
    onSuccess: (receipt) => {
      toast.success('Fatura confirmada.');
      invalidate(receipt.id);
    },
    onError: report,
  });
}

export function useReopenReceipt() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (receiptId: string) => api.post<ReceiptDetail>(`/receipts/${receiptId}/reopen`),
    onSuccess: (receipt) => {
      toast.success('Fatura reaberta para revisão.');
      invalidate(receipt.id);
    },
    onError: report,
  });
}

export function useVoidReceipt() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ receiptId, reason }: { receiptId: string; reason: string }) =>
      api.post<ReceiptDetail>(`/receipts/${receiptId}/void`, { reason }),
    onSuccess: (receipt) => {
      toast.success('Fatura anulada.');
      invalidate(receipt.id);
    },
    onError: report,
  });
}

export function useUpdateReceipt() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ receiptId, patch }: { receiptId: string; patch: Record<string, unknown> }) =>
      api.patch<ReceiptDetail>(`/receipts/${receiptId}`, patch),
    onSuccess: (receipt) => invalidate(receipt.id),
    onError: report,
  });
}

export function useUpdateItem() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({
      receiptId,
      itemId,
      patch,
    }: {
      receiptId: string;
      itemId: string;
      patch: Record<string, unknown>;
    }) => api.patch<ReceiptDetail>(`/receipts/${receiptId}/items/${itemId}`, patch),
    onSuccess: (receipt) => invalidate(receipt.id),
    onError: report,
  });
}

export function useAddFsItem() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ receiptId, body }: { receiptId: string; body: Record<string, unknown> }) =>
      api.post<ReceiptDetail>(`/receipts/${receiptId}/items`, body),
    onSuccess: (receipt) => {
      toast.success('Artigo Fs adicionado. Nenhum valor impresso foi alterado.');
      invalidate(receipt.id);
    },
    onError: report,
  });
}

export function useDeleteItem() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ receiptId, itemId }: { receiptId: string; itemId: string }) =>
      api.delete<ReceiptDetail>(`/receipts/${receiptId}/items/${itemId}`),
    onSuccess: (receipt) => invalidate(receipt.id),
    onError: report,
  });
}

export function useSaveProfile() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ profileId, patch }: { profileId: string; patch: Record<string, unknown> }) =>
      api.patch<ParserProfile>(`/parser-profiles/${profileId}`, patch),
    onSuccess: () => {
      toast.success('Perfil guardado.');
      invalidate();
    },
    onError: report,
  });
}
