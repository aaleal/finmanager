import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { api, ApiError, streamNdjson } from '@/lib/api';
import { useSession } from '@/features/auth/session';
import type {
  BricksetImport,
  LegoBricksetJob,
  LegoBulkImportPreview,
  LegoBulkImportRow,
  LegoBulkImportRowResult,
  LegoInstancePage,
  LegoOverview,
  LegoSetInstance,
  LegoSetModel,
  LookupResult,
  Page,
  StorageBulkImportResult,
  StorageLocation,
} from '@/lib/types';

export type InstanceFilters = {
  search?: string;
  theme?: string;
  storage_location_id?: string;
  storage_area?: string;
  build_state?: string;
  condition?: string;
  acquisition_source?: string;
  release_year?: string;
  ownership_status?: string;
  completeness?: string;
  retirement?: string;
  copies?: string;
  fs?: string;
  paid_min?: string;
  paid_max?: string;
  rrp_min?: string;
  rrp_max?: string;
  roi_min?: string;
  roi_max?: string;
  roi_basis?: string;
  sort?: string;
  direction?: string;
  page?: string;
  page_size?: string;
};

/** Every LEGO query key carries the active entity so switching invalidates cleanly. */
function useScope() {
  const { session } = useSession();
  return session?.active_entity_id ?? 'all';
}

export function useLegoOverview() {
  const scope = useScope();
  return useQuery({
    queryKey: ['lego', 'overview', scope],
    queryFn: () => api.get<LegoOverview>('/lego/overview'),
  });
}

export function useInstances(filters: InstanceFilters) {
  const scope = useScope();
  return useQuery({
    queryKey: ['lego', 'instances', scope, filters],
    queryFn: () =>
      api.get<LegoInstancePage>('/lego/instances', {
        search: filters.search,
        theme: filters.theme,
        storage_location_id: filters.storage_location_id,
        storage_area: filters.storage_area,
        build_state: filters.build_state,
        condition: filters.condition,
        acquisition_source: filters.acquisition_source,
        release_year: filters.release_year,
        ownership_status: filters.ownership_status,
        completeness: filters.completeness ?? 'all',
        retirement: filters.retirement ?? 'all',
        copies: filters.copies ?? 'all',
        fs: filters.fs ?? 'all',
        paid_min: filters.paid_min,
        paid_max: filters.paid_max,
        rrp_min: filters.rrp_min,
        rrp_max: filters.rrp_max,
        roi_min: filters.roi_min,
        roi_max: filters.roi_max,
        roi_basis: filters.roi_basis ?? 'cost',
        sort: filters.sort ?? 'created',
        direction: filters.direction ?? 'desc',
        page: filters.page ?? '1',
        page_size: filters.page_size ?? '25',
      }),
    placeholderData: (previous) => previous,
  });
}

export function useModels(params: {
  search?: string;
  stale_only?: boolean;
  no_value_only?: boolean;
}) {
  const scope = useScope();
  return useQuery({
    queryKey: ['lego', 'models', scope, params],
    queryFn: () =>
      api.get<Page<LegoSetModel>>('/lego/models', {
        search: params.search,
        stale_only: params.stale_only || undefined,
        no_value_only: params.no_value_only || undefined,
        page_size: 200,
      }),
  });
}

export function useModelInstances(modelId: string | null) {
  const scope = useScope();
  return useQuery({
    queryKey: ['lego', 'model-instances', scope, modelId],
    queryFn: () => api.get<LegoSetInstance[]>(`/lego/models/${modelId}/instances`),
    enabled: Boolean(modelId),
  });
}

export function useStorageLocations() {
  const scope = useScope();
  return useQuery({
    queryKey: ['lego', 'storage', scope],
    queryFn: () => api.get<StorageLocation[]>('/lego/storage-locations'),
  });
}

export function useInvalidateLego() {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: ['lego'] });
    queryClient.invalidateQueries({ queryKey: ['dashboard'] });
  };
}

function errorMessage(error: unknown, fallback: string) {
  return error instanceof ApiError ? error.message : fallback;
}

export function useLookup() {
  return useMutation({
    mutationFn: (setNumber: string) =>
      api.post<LookupResult>('/lego/models/lookup', { set_number: setNumber }),
  });
}

export function useCreateInstance() {
  const invalidate = useInvalidateLego();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      api.post<LegoSetInstance>('/lego/instances', payload),
    onSuccess: () => {
      toast.success('Cópia registada.');
      invalidate();
    },
    onError: (error) => toast.error(errorMessage(error, 'Não foi possível registar a cópia.')),
  });
}

export function useUpdateInstance() {
  const invalidate = useInvalidateLego();
  return useMutation({
    mutationFn: ({ id, ...payload }: { id: string } & Record<string, unknown>) =>
      api.patch<LegoSetInstance>(`/lego/instances/${id}`, payload),
    onSuccess: () => {
      toast.success('Cópia atualizada.');
      invalidate();
    },
    onError: (error) => toast.error(errorMessage(error, 'Não foi possível atualizar a cópia.')),
  });
}

export function useDeleteInstance() {
  const invalidate = useInvalidateLego();
  return useMutation({
    mutationFn: ({ id, hard }: { id: string; hard?: boolean }) =>
      api.delete(`/lego/instances/${id}`, { hard: hard ? true : undefined }),
    onSuccess: () => {
      toast.success('Cópia eliminada.');
      invalidate();
    },
    onError: (error) => toast.error(errorMessage(error, 'Não foi possível eliminar a cópia.')),
  });
}

export function useUpdateModel() {
  const invalidate = useInvalidateLego();
  return useMutation({
    mutationFn: ({ id, ...payload }: { id: string } & Record<string, unknown>) =>
      api.patch<LegoSetModel>(`/lego/models/${id}`, payload),
    onSuccess: () => {
      toast.success('Conjunto atualizado.');
      invalidate();
    },
    onError: (error) => toast.error(errorMessage(error, 'Não foi possível atualizar o conjunto.')),
  });
}

export function useDeleteModel() {
  const invalidate = useInvalidateLego();
  return useMutation({
    mutationFn: ({ id, hard }: { id: string; hard?: boolean }) =>
      api.delete(`/lego/models/${id}`, { hard: hard ? true : undefined }),
    onSuccess: () => {
      toast.success('Conjunto eliminado do catálogo.');
      invalidate();
    },
    onError: (error) => toast.error(errorMessage(error, 'Não foi possível eliminar o conjunto.')),
  });
}

export function useExportCollection() {
  return useMutation({
    mutationFn: () => api.download('/lego/export.xlsx'),
    onSuccess: () => toast.success('Ficheiro exportado.'),
    onError: (error) => toast.error(errorMessage(error, 'Não foi possível exportar a coleção.')),
  });
}

export function useSetInstancePhoto() {
  const invalidate = useInvalidateLego();
  return useMutation({
    mutationFn: async ({ id, file, url }: { id: string; file?: File; url?: string }) => {
      if (file) {
        const formData = new FormData();
        formData.append('file', file);
        return api.upload<LegoSetInstance>(`/lego/instances/${id}/photo`, formData);
      }
      return api.put<LegoSetInstance>(`/lego/instances/${id}/photo`, undefined, { url });
    },
    onSuccess: () => {
      toast.success('Fotografia guardada localmente.');
      invalidate();
    },
    onError: (error) => toast.error(errorMessage(error, 'Não foi possível guardar a imagem.')),
  });
}

/** Which of the set's own images (cover or gallery) stands for this copy in the table. */
export function useSetInstanceDisplayImage() {
  const invalidate = useInvalidateLego();
  return useMutation({
    mutationFn: ({ id, documentId }: { id: string; documentId: string | null }) =>
      api.put<LegoSetInstance>(`/lego/instances/${id}/display-image`, { document_id: documentId }),
    onSuccess: () => {
      toast.success('Imagem da cópia atualizada.');
      invalidate();
    },
    onError: (error) => toast.error(errorMessage(error, 'Não foi possível atualizar a imagem.')),
  });
}

export function useSetModelImage() {
  const invalidate = useInvalidateLego();
  return useMutation({
    mutationFn: async ({ id, file, url }: { id: string; file?: File; url?: string }) => {
      if (file) {
        const formData = new FormData();
        formData.append('file', file);
        return api.upload<LegoSetModel>(`/lego/models/${id}/image`, formData);
      }
      return api.put<LegoSetModel>(`/lego/models/${id}/image`, undefined, { url });
    },
    onSuccess: () => {
      toast.success('Imagem guardada localmente.');
      invalidate();
    },
    onError: (error) => toast.error(errorMessage(error, 'Não foi possível guardar a imagem.')),
  });
}

/** Add / remove / promote the extra views that make up a set's carousel. */
export function useSetGallery() {
  const invalidate = useInvalidateLego();

  const add = useMutation({
    mutationFn: async ({
      id,
      file,
      url,
      caption,
    }: {
      id: string;
      file?: File;
      url?: string;
      caption?: string;
    }) => {
      if (file) {
        const formData = new FormData();
        formData.append('file', file);
        return api.upload<LegoSetModel>(`/lego/models/${id}/images`, formData, { caption }, 'POST');
      }
      return api.post<LegoSetModel>(`/lego/models/${id}/images`, undefined, { url, caption });
    },
    onSuccess: () => {
      toast.success('Imagem adicionada à galeria.');
      invalidate();
    },
    onError: (error) => toast.error(errorMessage(error, 'Não foi possível adicionar a imagem.')),
  });

  const promote = useMutation({
    mutationFn: ({ id, imageId }: { id: string; imageId: string }) =>
      api.post<LegoSetModel>(`/lego/models/${id}/images/${imageId}/cover`),
    onSuccess: () => {
      toast.success('Imagem principal alterada.');
      invalidate();
    },
    onError: (error) => toast.error(errorMessage(error, 'Não foi possível alterar a capa.')),
  });

  const remove = useMutation({
    mutationFn: ({ id, imageId }: { id: string; imageId: string }) =>
      api.delete<LegoSetModel>(`/lego/models/${id}/images/${imageId}`),
    onSuccess: () => {
      toast.success('Imagem removida.');
      invalidate();
    },
    onError: (error) => toast.error(errorMessage(error, 'Não foi possível remover a imagem.')),
  });

  return { add, promote, remove };
}

/** Manuals and info booklets: pulled from Brickset, then served from disk. */
export function useSetInstructions() {
  const invalidate = useInvalidateLego();

  const importFromBrickset = useMutation({
    mutationFn: (id: string) => api.post<BricksetImport>(`/lego/models/${id}/brickset`),
    onSuccess: (result) => {
      toast.success(
        result.message ??
          `${result.images_added} imagem(ns) e ${result.instructions_added} manual(is) guardados localmente.`,
      );
      invalidate();
    },
    onError: (error) => toast.error(errorMessage(error, 'Não foi possível importar do Brickset.')),
  });

  const remove = useMutation({
    mutationFn: ({ id, instructionId }: { id: string; instructionId: string }) =>
      api.delete<LegoSetModel>(`/lego/models/${id}/instructions/${instructionId}`),
    onSuccess: () => {
      toast.success('Manual removido.');
      invalidate();
    },
    onError: (error) => toast.error(errorMessage(error, 'Não foi possível remover o manual.')),
  });

  const add = useMutation({
    mutationFn: async ({
      id,
      description,
      file,
      url,
      language,
    }: {
      id: string;
      description: string;
      file?: File;
      url?: string;
      language?: string;
    }) => {
      if (file) {
        const formData = new FormData();
        formData.append('file', file);
        return api.upload<LegoSetModel>(
          `/lego/models/${id}/instructions`,
          formData,
          { description, language },
          'POST',
        );
      }
      return api.post<LegoSetModel>(`/lego/models/${id}/instructions`, undefined, {
        description,
        url,
        language,
      });
    },
    onSuccess: () => {
      toast.success('Manual adicionado.');
      invalidate();
    },
    onError: (error) => toast.error(errorMessage(error, 'Não foi possível adicionar o manual.')),
  });

  return { importFromBrickset, add, remove };
}

/** Queues the images/manuals fetch as two background jobs (ADR-0049) instead of
 * downloading them inline — this is what the automatic import fired once from
 * set creation calls now. Fast (DB-only), so it's safe to fire-and-forget. */
export function useQueueBricksetAssets() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.post<LegoBricksetJob[]>(`/lego/models/${id}/brickset/queue`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['lego', 'brickset-jobs'] });
    },
  });
}

const ACTIVE_JOB_STATUSES = new Set(['QUEUED', 'RUNNING']);

/** Visibility panel data: polls while at least one job is still queued/running,
 * stops polling once everything has settled (succeeded/failed/cancelled). */
export function useBricksetJobs() {
  return useQuery({
    queryKey: ['lego', 'brickset-jobs'],
    queryFn: () => api.get<LegoBricksetJob[]>('/lego/brickset-jobs'),
    refetchInterval: (query) => {
      const jobs = query.state.data;
      return jobs?.some((job) => ACTIVE_JOB_STATUSES.has(job.status)) ? 4000 : false;
    },
  });
}

export function useCancelBricksetJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.post<LegoBricksetJob>(`/lego/brickset-jobs/${id}/cancel`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['lego', 'brickset-jobs'] });
    },
    onError: (error) => toast.error(errorMessage(error, 'Não foi possível cancelar o processo.')),
  });
}

export function useRetryBricksetJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.post<LegoBricksetJob>(`/lego/brickset-jobs/${id}/retry`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['lego', 'brickset-jobs'] });
    },
    onError: (error) => toast.error(errorMessage(error, 'Não foi possível repetir o processo.')),
  });
}

export function useStorageMutations() {
  const invalidate = useInvalidateLego();

  const create = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      api.post<StorageLocation>('/lego/storage-locations', payload),
    onSuccess: () => {
      toast.success('Local criado.');
      invalidate();
    },
    onError: (error) => toast.error(errorMessage(error, 'Não foi possível criar o local.')),
  });

  const update = useMutation({
    mutationFn: ({ id, ...payload }: { id: string } & Record<string, unknown>) =>
      api.patch<StorageLocation>(`/lego/storage-locations/${id}`, payload),
    onSuccess: () => invalidate(),
    onError: (error) => toast.error(errorMessage(error, 'Não foi possível atualizar o local.')),
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.delete(`/lego/storage-locations/${id}`),
    onSuccess: () => {
      toast.success('Local eliminado.');
      invalidate();
    },
    onError: (error) => toast.error(errorMessage(error, 'Não foi possível eliminar o local.')),
  });

  return { create, update, remove };
}

/** Spreadsheet → preview table → commit, mirroring the manual add-copy flow one row
 * at a time (M9.5). Preview never contacts Brickset; only commit does. */
export function useBulkImportPreview() {
  return useMutation({
    mutationFn: (file: File) => {
      const formData = new FormData();
      formData.append('file', file);
      return api.upload<LegoBulkImportPreview>(
        '/lego/instances/bulk/preview',
        formData,
        undefined,
        'POST',
      );
    },
    onError: (error) => toast.error(errorMessage(error, 'Não foi possível ler o ficheiro.')),
  });
}

export function useBulkImportCommit() {
  const invalidate = useInvalidateLego();
  return useMutation({
    mutationFn: ({
      rows,
      onRow,
    }: {
      rows: LegoBulkImportRow[];
      onRow?: (result: LegoBulkImportRowResult) => void;
    }) =>
      streamNdjson<LegoBulkImportRowResult>('/lego/instances/bulk/commit', { rows }, (result) =>
        onRow?.(result),
      ),
    onSuccess: () => invalidate(),
    onError: (error) => toast.error(errorMessage(error, 'Não foi possível importar as cópias.')),
  });
}

export function useStorageBulkImport() {
  const invalidate = useInvalidateLego();
  return useMutation({
    mutationFn: (file: File) => {
      const formData = new FormData();
      formData.append('file', file);
      return api.upload<StorageBulkImportResult>(
        '/lego/storage-locations/bulk',
        formData,
        undefined,
        'POST',
      );
    },
    onSuccess: () => invalidate(),
    onError: (error) => toast.error(errorMessage(error, 'Não foi possível importar o ficheiro.')),
  });
}
