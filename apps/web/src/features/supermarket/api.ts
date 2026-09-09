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
    queryKey: ['supermarket', 'status', scope],
    queryFn: () => api.get<ReceiptStatusBoard>('/supermarket/status'),
    refetchInterval: 30_000,
  });
}

export function useReceiptQueue() {
  const scope = useScope();
  return useQuery({
    queryKey: ['supermarket', 'queue', scope],
    queryFn: () => api.get<QueueEntry[]>('/supermarket/queue'),
  });
}

export function useReceipts(filters: ReceiptFilters) {
  const scope = useScope();
  return useQuery({
    queryKey: ['supermarket', 'list', scope, filters],
    queryFn: () =>
      api.get<Page<ReceiptSummary>>('/supermarket', {
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
    queryKey: ['supermarket', 'detail', receiptId],
    queryFn: () => api.get<ReceiptDetail>(`/supermarket/${receiptId}`),
    enabled: Boolean(receiptId),
  });
}

export function useReceiptItems(filters: ItemFilters) {
  const scope = useScope();
  return useQuery({
    queryKey: ['supermarket-items', scope, filters],
    queryFn: () =>
      api.get<Page<ReceiptItem>>('/supermarket-items', {
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
    queryKey: ['supermarket-items', 'summary', scope, filters],
    queryFn: () =>
      api.get<Page<ProductSummary>>('/supermarket-items/summary', {
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
    queryKey: ['supermarket', 'parser-profiles'],
    queryFn: () => api.get<ParserProfile[]>('/parser-profiles'),
  });
}

export function useParserOptions() {
  return useQuery({
    queryKey: ['supermarket', 'parsers'],
    queryFn: () => api.get<ParserOption[]>('/parser-profiles/parsers'),
    staleTime: Infinity,
  });
}

/** Invalidate the item, the queue, the list and the status board — never a partial. */
function useInvalidate() {
  const queryClient = useQueryClient();
  return (receiptId?: string) => {
    void queryClient.invalidateQueries({ queryKey: ['supermarket'] });
    void queryClient.invalidateQueries({ queryKey: ['supermarket-items'] });
    void queryClient.invalidateQueries({ queryKey: ['review'] });
    if (receiptId) {
      void queryClient.invalidateQueries({ queryKey: ['supermarket', 'detail', receiptId] });
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
        '/supermarket',
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
        `/supermarket/${receiptId}/reparse`,
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
    mutationFn: (receiptId: string) => api.post<ReceiptDetail>(`/supermarket/${receiptId}/confirm`),
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
    mutationFn: (receiptId: string) => api.post<ReceiptDetail>(`/supermarket/${receiptId}/reopen`),
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
      api.post<ReceiptDetail>(`/supermarket/${receiptId}/void`, { reason }),
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
      api.patch<ReceiptDetail>(`/supermarket/${receiptId}`, patch),
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
    }) => api.patch<ReceiptDetail>(`/supermarket/${receiptId}/items/${itemId}`, patch),
    onSuccess: (receipt) => invalidate(receipt.id),
    onError: report,
  });
}

export function useAddFsItem() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ receiptId, body }: { receiptId: string; body: Record<string, unknown> }) =>
      api.post<ReceiptDetail>(`/supermarket/${receiptId}/items`, body),
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
      api.delete<ReceiptDetail>(`/supermarket/${receiptId}/items/${itemId}`),
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
