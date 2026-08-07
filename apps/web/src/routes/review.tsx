import { useQuery } from '@tanstack/react-query';
import { Inbox } from 'lucide-react';
import { api } from '@/lib/api';
import { useSession } from '@/features/auth/session';
import type { Page, ReviewTask } from '@/lib/types';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { EmptyState, PageHeader, Skeleton } from '@/components/ui/feedback';
import { dateTime } from '@/lib/format';

/**
 * The shared Review Queue shell (orchestrator §3 Frontend).
 *
 * One generic component driven entirely by `{subject_type, module, confidence,
 * suggested_payload, decision_reasons}` — every ingestion module plugs into it
 * without a bespoke screen.
 */
export function ReviewPage() {
  const { session, canWrite } = useSession();

  const tasks = useQuery({
    queryKey: ['review', 'tasks', session?.active_entity_id ?? 'all'],
    queryFn: () => api.get<Page<ReviewTask>>('/review/tasks', { status: 'PENDING' }),
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Fila de revisão"
        description="Só chega aqui o que o sistema não conseguiu decidir com confiança suficiente."
      />

      {tasks.isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <Skeleton key={index} className="h-24 rounded-xl" />
          ))}
        </div>
      ) : tasks.data?.items.length ? (
        <div className="space-y-3">
          {tasks.data.items.map((task) => (
            <Card key={task.id}>
              <CardHeader className="pb-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <CardTitle>{task.title ?? task.subject_type}</CardTitle>
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary">{task.module}</Badge>
                    {task.confidence !== null ? (
                      <Badge variant={task.confidence >= 0.6 ? 'warning' : 'destructive'}>
                        confiança {Math.round(task.confidence * 100)} %
                      </Badge>
                    ) : null}
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-xs text-muted-foreground">{dateTime(task.created_at)}</p>
                {task.decision_reasons.length ? (
                  <ul className="space-y-1 text-sm">
                    {task.decision_reasons.map((reason, index) => (
                      <li key={index} className="text-muted-foreground">
                        {JSON.stringify(reason)}
                      </li>
                    ))}
                  </ul>
                ) : null}
                {canWrite ? (
                  <div className="flex gap-2">
                    <Button size="sm">Confirmar</Button>
                    <Button size="sm" variant="outline">
                      Corrigir
                    </Button>
                    <Button size="sm" variant="ghost">
                      Descartar
                    </Button>
                  </div>
                ) : null}
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={Inbox}
          title="Nada por rever"
          description="A coleção LEGO é totalmente manual, por desenho — não gera tarefas de revisão. Esta fila enche-se quando os talões, extratos bancários e faturas começarem a ser processados."
        />
      )}
    </div>
  );
}
