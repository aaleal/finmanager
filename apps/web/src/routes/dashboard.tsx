import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowRight, Blocks, Inbox, Sparkles } from 'lucide-react';
import { api } from '@/lib/api';
import { useSession } from '@/features/auth/session';
import type { Dashboard } from '@/lib/types';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { PageHeader, Skeleton } from '@/components/ui/feedback';
import { dateTime, eur } from '@/lib/format';

const AUDIT_LABELS: Record<string, string> = {
  CREATE: 'criou',
  UPDATE: 'atualizou',
  DELETE: 'eliminou',
  STATUS_CHANGE: 'alterou o estado de',
};

const TABLE_LABELS: Record<string, string> = {
  lego_set_models: 'um conjunto LEGO',
  lego_set_instances: 'uma cópia LEGO',
  lego_storage_locations: 'um local de arrumação',
  entities: 'uma entidade',
  users: 'um utilizador',
  merchants: 'um comerciante',
  household_members: 'um membro',
};

export function DashboardPage() {
  const { session, activeEntity } = useSession();

  const dashboard = useQuery({
    queryKey: ['dashboard', session?.active_entity_id ?? 'all'],
    queryFn: () => api.get<Dashboard>('/dashboard'),
  });

  const greeting = new Date().getHours() < 13 ? 'Bom dia' : new Date().getHours() < 20 ? 'Boa tarde' : 'Boa noite';

  return (
    <div className="space-y-6">
      <PageHeader
        title={`${greeting}, ${session?.user.display_name?.split(' ')[0] ?? ''}`}
        description={
          activeEntity
            ? `A ver os dados de ${activeEntity.name}.`
            : 'A ver os dados de todo o agregado.'
        }
      />

      {dashboard.isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-28 rounded-xl" />
          ))}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {dashboard.data?.tiles.map((tile) => {
            const live = tile.status === 'LIVE';
            const content = (
              <Card
                className={
                  live
                    ? 'h-full transition hover:-translate-y-0.5 hover:shadow-card'
                    : 'h-full border-dashed bg-card/40'
                }
              >
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between gap-2">
                    <CardTitle className={live ? '' : 'text-muted-foreground'}>
                      {tile.label}
                    </CardTitle>
                    {live ? (
                      <ArrowRight className="size-4 text-muted-foreground" />
                    ) : (
                      <Badge variant="muted">em breve</Badge>
                    )}
                  </div>
                </CardHeader>
                <CardContent>
                  {live ? (
                    <div className="flex items-end justify-between gap-3">
                      <div>
                        <p className="numeric text-2xl font-semibold">
                          {eur(tile.primary_value)}
                        </p>
                        <p className="text-xs text-muted-foreground">{tile.primary_label}</p>
                      </div>
                      <div className="text-right">
                        <p className="numeric text-lg font-medium">{tile.secondary_value}</p>
                        <p className="text-xs text-muted-foreground">{tile.secondary_label}</p>
                      </div>
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      Este módulo chega numa fase seguinte.
                    </p>
                  )}
                </CardContent>
              </Card>
            );
            return live && tile.href ? (
              <Link key={tile.key} to={tile.href} className="rounded-xl">
                {content}
              </Link>
            ) : (
              <div key={tile.key}>{content}</div>
            );
          })}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Atividade recente</CardTitle>
          </CardHeader>
          <CardContent>
            {dashboard.data?.recent_activity.length ? (
              <ul className="divide-y divide-border">
                {dashboard.data.recent_activity.map((item) => (
                  <li key={item.id} className="flex items-center justify-between gap-4 py-2.5 text-sm">
                    <span className="min-w-0 truncate">
                      Alguém {AUDIT_LABELS[item.action] ?? item.action.toLowerCase()}{' '}
                      <span className="font-medium">
                        {TABLE_LABELS[item.table_name] ?? item.table_name}
                      </span>
                    </span>
                    <time className="shrink-0 text-xs text-muted-foreground">
                      {dateTime(item.created_at)}
                    </time>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="py-6 text-center text-sm text-muted-foreground">
                Ainda não há atividade registada.
              </p>
            )}
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Inbox className="size-4 text-muted-foreground" />
                Fila de revisão
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="numeric text-3xl font-semibold">
                {dashboard.data?.pending_reviews ?? 0}
              </p>
              <p className="text-sm text-muted-foreground">
                Decisões automáticas à espera de confirmação. Enche-se quando os módulos de
                ingestão entrarem em funcionamento.
              </p>
              <Button asChild variant="outline" size="sm">
                <Link to="/revisao">Abrir fila</Link>
              </Button>
            </CardContent>
          </Card>

          <Card className="border-primary/25 bg-primary/[0.04]">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="size-4 text-primary" />
                Nesta fase
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-muted-foreground">
              <p>
                A fundação (agregado, entidades, RBAC, auditoria) e a{' '}
                <Link to="/lego" className="font-medium text-primary hover:underline">
                  coleção LEGO
                </Link>{' '}
                estão completas.
              </p>
              <Button asChild size="sm" variant="secondary">
                <Link to="/lego">
                  <Blocks className="size-4" />
                  Ver a coleção
                </Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
