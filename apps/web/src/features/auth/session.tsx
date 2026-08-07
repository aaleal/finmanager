import * as React from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, onUnauthorized, setCsrfToken } from '@/lib/api';
import type { Entity, SessionInfo } from '@/lib/types';

interface SessionContextValue {
  session: SessionInfo | null;
  entities: Entity[];
  isLoading: boolean;
  activeEntityId: string | null;
  activeEntity: Entity | null;
  canWrite: boolean;
  isOwner: boolean;
  setActiveEntity: (entityId: string | null) => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<unknown>;
}

const SessionContext = React.createContext<SessionContextValue | null>(null);

export const ENTITY_STORAGE_KEY = 'finmanager.entity';

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();

  const sessionQuery = useQuery({
    queryKey: ['session'],
    queryFn: () => api.get<SessionInfo>('/auth/me'),
    retry: false,
    staleTime: 60_000,
  });

  const session = sessionQuery.isError ? null : (sessionQuery.data ?? null);

  React.useEffect(() => {
    if (session?.csrf_token) setCsrfToken(session.csrf_token);
  }, [session?.csrf_token]);

  React.useEffect(
    () =>
      onUnauthorized(() => {
        setCsrfToken(null);
        queryClient.setQueryData(['session'], null);
      }),
    [queryClient],
  );

  const entitiesQuery = useQuery({
    queryKey: ['entities'],
    queryFn: () => api.get<Entity[]>('/entities'),
    enabled: Boolean(session),
    staleTime: 5 * 60_000,
  });

  const switchEntity = useMutation({
    mutationFn: (entityId: string | null) =>
      api.post<{ active_entity_id: string | null; csrf_token: string }>('/sessions/entity', {
        entity_id: entityId,
      }),
    onSuccess: (result) => {
      setCsrfToken(result.csrf_token);
      queryClient.setQueryData<SessionInfo | null>(['session'], (previous) =>
        previous
          ? {
              ...previous,
              active_entity_id: result.active_entity_id,
              csrf_token: result.csrf_token,
            }
          : previous,
      );
      // Every module query is keyed by the active entity, so drop the module caches.
      queryClient.invalidateQueries({ predicate: (q) => q.queryKey[0] !== 'session' });
    },
  });

  const loginMutation = useMutation({
    mutationFn: (payload: { email: string; password: string }) =>
      api.post<SessionInfo>('/auth/login', payload),
    onSuccess: (result) => {
      setCsrfToken(result.csrf_token);
      queryClient.setQueryData(['session'], result);
      queryClient.invalidateQueries();
    },
  });

  const logoutMutation = useMutation({
    mutationFn: () => api.post('/auth/logout'),
    onSettled: () => {
      setCsrfToken(null);
      queryClient.clear();
      queryClient.setQueryData(['session'], null);
    },
  });

  const entities = React.useMemo(() => entitiesQuery.data ?? [], [entitiesQuery.data]);
  const activeEntityId = session?.active_entity_id ?? null;

  const value = React.useMemo<SessionContextValue>(
    () => ({
      session,
      entities,
      isLoading: sessionQuery.isLoading,
      activeEntityId,
      activeEntity: entities.find((entity) => entity.id === activeEntityId) ?? null,
      canWrite: session?.role === 'OWNER' || session?.role === 'MEMBER',
      isOwner: session?.role === 'OWNER',
      setActiveEntity: async (entityId) => {
        window.localStorage.setItem(ENTITY_STORAGE_KEY, entityId ?? '');
        await switchEntity.mutateAsync(entityId);
      },
      login: async (email, password) => {
        await loginMutation.mutateAsync({ email, password });
      },
      logout: async () => {
        await logoutMutation.mutateAsync();
      },
      refresh: () => queryClient.invalidateQueries({ queryKey: ['session'] }),
    }),
    [
      session,
      entities,
      sessionQuery.isLoading,
      activeEntityId,
      switchEntity,
      loginMutation,
      logoutMutation,
      queryClient,
    ],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const context = React.useContext(SessionContext);
  if (!context) throw new Error('useSession tem de ser usado dentro de <SessionProvider>');
  return context;
}
