import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ExternalLink, Inbox } from 'lucide-react';
import { toast } from 'sonner';
import { api, ApiError } from '@/lib/api';
import { useSession } from '@/features/auth/session';
import type { Page, ReviewTask } from '@/lib/types';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { EmptyState, Skeleton } from '@/components/ui/feedback';
import { WhyPopover } from '@/features/supermarket/why-popover';
import { dateTime } from '@/lib/format';

/**
 * The shared Review Queue (orchestrator §3 Frontend, §5a rule 2).
 *
 * **There is exactly one of these.** It is generic over
 * `{subject_type, subject_id, module, confidence, suggested_payload,
 * decision_reasons}`, so a module never builds its own review surface — it
 * produces `ReviewTask` rows and registers where a subject opens. Anything that
 * looks like a second queue is a defect.
 */

type Resolution = 'CONFIRMED' | 'FIXED' | 'DISMISSED';

/**
 * Where a subject is resolved in its owning module.
 *
 * "Fix" deliberately does not inline-edit a receipt here: a receipt is reviewed
 * against its original document in the crown-jewel split pane, so this queue
 * hands the task over instead of reproducing that screen badly.
 */
const SUBJECT_ROUTES: Record<string, (task: ReviewTask) => string> = {
  Receipt: (task) => `/supermercado?tab=faturas&receipt=${task.subject_id}`,
};

const MODULE_LABELS: Record<string, string> = {
  receipts: 'Supermercado',
  banking: 'Banco',
  health: 'Saúde',
  utilities: 'Utilities',
  vehicles: 'Veículos',
  lego: 'LEGO',
};

function useResolveTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ taskId, action }: { taskId: string; action: Resolution }) =>
      api.post<ReviewTask>(`/review/tasks/${taskId}/resolve`, { action }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['review'] });
      void queryClient.invalidateQueries({ queryKey: ['supermarket'] });
    },
    onError: (error: unknown) =>
      toast.error(
        error instanceof ApiError ? error.message : 'Não foi possível resolver a tarefa.',
      ),
  });
}

export function ReviewQueue({ module }: { module?: string }) {
  const { session, canWrite } = useSession();
  const navigate = useNavigate();
  const resolve = useResolveTask();

  const tasks = useQuery({
    queryKey: ['review', 'tasks', session?.active_entity_id ?? 'all', module ?? 'all'],
    queryFn: () =>
      api.get<Page<ReviewTask>>('/review/tasks', { status: 'PENDING', module, page_size: '50' }),
  });

  if (tasks.isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, index) => (
          <Skeleton key={index} className="h-24 rounded-xl" />
        ))}
      </div>
    );
  }

  if (!tasks.data?.items.length) {
    return (
      <EmptyState
        icon={Inbox}
        title="Nada por rever"
        description="Só chega aqui o que o sistema não conseguiu decidir com confiança suficiente. Uma fila vazia significa que tudo foi aceite automaticamente."
      />
    );
  }

  return (
    <div className="space-y-3">
      {tasks.data.items.map((task) => {
        const openIn = SUBJECT_ROUTES[task.subject_type];
        return (
          <Card key={task.id}>
            <CardHeader className="pb-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <CardTitle>{task.title ?? task.subject_type}</CardTitle>
                <div className="flex items-center gap-2">
                  <Badge variant="secondary">{MODULE_LABELS[task.module] ?? task.module}</Badge>
                  {task.confidence !== null ? (
                    <Badge variant={task.confidence >= 0.6 ? 'warning' : 'destructive'}>
                      confiança {Math.round(task.confidence * 100)} %
                    </Badge>
                  ) : null}
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap items-center gap-3">
                <p className="text-xs text-muted-foreground">{dateTime(task.created_at)}</p>
                <WhyPopover reasons={task.decision_reasons} />
              </div>
              <div className="flex flex-wrap gap-2">
                {openIn ? (
                  <Button size="sm" variant="outline" onClick={() => navigate(openIn(task))}>
                    <ExternalLink />
                    Abrir no módulo
                  </Button>
                ) : null}
                {canWrite ? (
                  <>
                    <Button
                      size="sm"
                      loading={resolve.isPending}
                      onClick={() => resolve.mutate({ taskId: task.id, action: 'CONFIRMED' })}
                    >
                      Confirmar
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      loading={resolve.isPending}
                      onClick={() => resolve.mutate({ taskId: task.id, action: 'DISMISSED' })}
                    >
                      Descartar
                    </Button>
                  </>
                ) : null}
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
