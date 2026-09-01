import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { api, ApiError } from '@/lib/api';

// Manually declared: these endpoints exist before `schema.d.ts` is regenerated
// against them (ADR-0037). Replace with `Schemas['...']` once `./fm types-gen`
// has run against the rebuilt API.
export interface BackupModule {
  key: string;
  label: string;
}

export interface ModuleBackupReport {
  module: string;
  label: string;
  counts: Record<string, number>;
  skipped: Record<string, number>;
}

export interface BackupImportReport {
  modules: ModuleBackupReport[];
}

function errorMessage(error: unknown, fallback: string) {
  return error instanceof ApiError ? error.message : fallback;
}

export function useBackupModules() {
  return useQuery({
    queryKey: ['settings', 'backup-modules'],
    queryFn: () => api.get<BackupModule[]>('/settings/backup/modules'),
  });
}

export function useExportBackup() {
  return useMutation({
    mutationFn: (module: string) => api.download('/settings/backup.zip', { module }),
    onSuccess: () => toast.success('Cópia de segurança criada.'),
    onError: (error) => toast.error(errorMessage(error, 'Não foi possível criar a cópia.')),
  });
}

function totalOf(counts: Record<string, number>) {
  return Object.values(counts).reduce((sum, value) => sum + value, 0);
}

export function useImportBackup() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => {
      const formData = new FormData();
      formData.append('file', file);
      // `api.upload` defaults to PUT, which this endpoint does not answer.
      return api.upload<BackupImportReport>('/settings/backup', formData, undefined, 'POST');
    },
    onSuccess: (report) => {
      const summary = report.modules
        .map((entry) => `${entry.label}: ${totalOf(entry.counts)} registo(s)`)
        .join(' · ');
      toast.success(`Cópia restaurada. ${summary}`);
      // Any module could have been restored, so every query is stale.
      void queryClient.invalidateQueries();
    },
    onError: (error) => toast.error(errorMessage(error, 'Não foi possível importar o arquivo.')),
  });
}
