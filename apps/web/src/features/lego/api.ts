import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { api, ApiError } from '@/lib/api';
import { useSession } from '@/features/auth/session';
import type {
  LegoOverview,
  LegoSetInstance,
  LegoSetModel,
  LookupResult,
  Page,
  StorageLocation,
} from '@/lib/types';

export type InstanceFilters = {
  search?: string;
  theme?: string;
  storage_location_id?: string;
  build_state?: string;
  condition?: string;
  ownership_status?: string;
  incomplete_only?: string;
  retired_only?: string;
  sort?: string;
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
      api.get<Page<LegoSetInstance>>('/lego/instances', {
        search: filters.search,
        theme: filters.theme,
        storage_location_id: filters.storage_location_id,
        build_state: filters.build_state,
        condition: filters.condition,
        ownership_status: filters.ownership_status,
        incomplete_only: filters.incomplete_only === '1' ? true : undefined,
        retired_only: filters.retired_only === '1' ? true : undefined,
        sort: filters.sort,
        page: filters.page ?? '1',
        page_size: filters.page_size ?? '25',
      }),
    placeholderData: (previous) => previous,
  });
}

export function useModels(params: { search?: string; stale_only?: boolean; no_value_only?: boolean }) {
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
    onSuccess: () => invalidate(),
    onError: (error) => toast.error(errorMessage(error, 'Não foi possível atualizar o conjunto.')),
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
