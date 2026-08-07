import * as React from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  AlertTriangle,
  Blocks,
  Boxes,
  Coins,
  Layers,
  PackageCheck,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';
import type { LegoOverview, LegoSetInstance } from '@/lib/types';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/feedback';
import { eur, eurCompact, num, percent, relativeDays, signedEur } from '@/lib/format';
import { cn } from '@/lib/utils';

const THEME_COLORS = [
  '#2563eb',
  '#0d9488',
  '#c026d3',
  '#ea580c',
  '#65a30d',
  '#7c3aed',
  '#0891b2',
  '#db2777',
];

function KpiCard({
  icon: Icon,
  label,
  value,
  hint,
  tone = 'default',
  onClick,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: React.ReactNode;
  hint?: React.ReactNode;
  tone?: 'default' | 'positive' | 'negative';
  onClick?: () => void;
}) {
  // A card without a destination is not a control, so it must not be a <button>.
  const Wrapper = onClick ? 'button' : 'div';
  return (
    <Wrapper
      {...(onClick ? { type: 'button' as const, onClick } : {})}
      className={cn(
        'rounded-xl border border-border bg-card p-4 text-left shadow-soft transition',
        onClick && 'cursor-pointer hover:-translate-y-0.5 hover:shadow-card',
      )}
    >
      <div className="flex items-center gap-2 text-muted-foreground">
        <Icon className="size-4" />
        <span className="text-xs font-medium uppercase tracking-wide">{label}</span>
      </div>
      <p
        className={cn(
          'numeric mt-2 text-2xl font-semibold tracking-tight',
          tone === 'positive' && 'text-success',
          tone === 'negative' && 'text-destructive',
        )}
      >
        {value}
      </p>
      {hint ? <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p> : null}
    </Wrapper>
  );
}

function MoverRow({ instance, rank }: { instance: LegoSetInstance; rank: number }) {
  const positive = Number(instance.appreciation_eur ?? 0) >= 0;
  return (
    <li className="flex items-center gap-3 py-2">
      <span className="w-4 shrink-0 text-xs text-muted-foreground">{rank}</span>
      <div className="size-9 shrink-0 overflow-hidden rounded-md border border-border bg-muted">
        {instance.set_model?.image_url ? (
          <img
            src={instance.set_model.image_url}
            alt=""
            className="size-full object-contain"
            loading="lazy"
          />
        ) : null}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{instance.set_model?.name}</p>
        <p className="truncate text-xs text-muted-foreground">
          {instance.set_model?.set_number ?? 'MOC'} · {eur(instance.acquisition_cost_eur)}
        </p>
      </div>
      <div className="shrink-0 text-right">
        <p className={cn('numeric text-sm font-semibold', positive ? 'text-success' : 'text-destructive')}>
          {signedEur(instance.appreciation_eur)}
        </p>
        <p className="text-xs text-muted-foreground">{percent(instance.roi_pct)}</p>
      </div>
    </li>
  );
}

export function LegoOverviewPanel({
  overview,
  isLoading,
  onFilter,
}: {
  overview: LegoOverview | undefined;
  isLoading: boolean;
  onFilter: (patch: Record<string, string | undefined>) => void;
}) {
  if (isLoading || !overview) {
    return (
      <div className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 8 }).map((_, index) => (
            <Skeleton key={index} className="h-24 rounded-xl" />
          ))}
        </div>
        <Skeleton className="h-80 rounded-xl" />
      </div>
    );
  }

  const gainPositive = Number(overview.unrealized_gain_eur) >= 0;
  const chartData = overview.themes.slice(0, 8).map((theme) => ({
    theme: theme.theme,
    valor: Number(theme.value_eur),
    custo: Number(theme.cost_eur),
    copies: theme.copies,
  }));

  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          icon={Coins}
          label="Custo total"
          value={eur(overview.total_cost_eur)}
          hint={`${overview.copies_owned} cópias na coleção`}
        />
        <KpiCard
          icon={TrendingUp}
          label="Valor atual"
          value={eur(overview.total_value_eur)}
          hint={
            overview.models_without_value > 0
              ? `${overview.models_without_value} conjunto(s) sem valor definido`
              : 'todos os conjuntos avaliados'
          }
          onClick={
            overview.models_without_value > 0 ? () => onFilter({ tab: 'colecao' }) : undefined
          }
        />
        <KpiCard
          icon={gainPositive ? TrendingUp : TrendingDown}
          label="Ganho não realizado"
          value={signedEur(overview.unrealized_gain_eur)}
          tone={gainPositive ? 'positive' : 'negative'}
          hint="Valor atual − custo, só de conjuntos avaliados"
        />
        <KpiCard
          icon={PackageCheck}
          label="ROI não realizado"
          value={percent(overview.roi_pct)}
          tone={overview.roi_pct && Number(overview.roi_pct) >= 0 ? 'positive' : 'negative'}
          hint="Prendas e conjuntos sem valor ficam de fora"
        />
        <KpiCard
          icon={Blocks}
          label="Conjuntos únicos"
          value={num(overview.unique_sets)}
          onClick={() => onFilter({ tab: 'colecao', agrupar: '1' })}
        />
        <KpiCard
          icon={Boxes}
          label="Cópias"
          value={num(overview.copies_owned)}
          onClick={() => onFilter({ tab: 'colecao' })}
        />
        <KpiCard icon={Layers} label="Peças" value={num(overview.total_pieces)} hint={`${num(overview.total_minifigs)} minifiguras`} />
        <KpiCard
          icon={AlertTriangle}
          label="Conjuntos retirados"
          value={num(overview.retired_sets)}
          onClick={() => onFilter({ tab: 'colecao', retired_only: '1' })}
        />
      </div>

      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-border bg-card px-4 py-3 text-sm">
        <span className="text-muted-foreground">
          Valores atualizados manualmente — o mais antigo é de{' '}
          <strong className="text-foreground">
            {relativeDays(overview.oldest_value_updated_at)}
          </strong>
          .
        </span>
        {overview.stale_value_models > 0 ? (
          <Badge variant="warning">
            <AlertTriangle />
            {overview.stale_value_models} com mais de {overview.stale_threshold_days} dias
          </Badge>
        ) : (
          <Badge variant="success">tudo dentro do prazo</Badge>
        )}
        {overview.stale_value_models > 0 ? (
          <Button
            size="sm"
            variant="outline"
            onClick={() => onFilter({ tab: 'colecao', stale: '1' })}
          >
            Ver conjuntos por atualizar
          </Button>
        ) : null}
      </div>

      <div className="grid gap-4 lg:grid-cols-5">
        <Card className="lg:col-span-3">
          <CardHeader>
            <CardTitle>Valor e cópias por tema</CardTitle>
            <CardDescription>
              Apenas cópias na coleção. Vendidos e oferecidos ficam fora, por desenho.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {chartData.length ? (
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" />
                    <XAxis
                      dataKey="theme"
                      tick={{ fontSize: 11 }}
                      stroke="hsl(var(--muted-foreground))"
                      interval={0}
                      angle={-18}
                      textAnchor="end"
                      height={54}
                    />
                    <YAxis
                      tick={{ fontSize: 11 }}
                      stroke="hsl(var(--muted-foreground))"
                      tickFormatter={(value: number) => eurCompact(value)}
                      width={62}
                    />
                    <RechartsTooltip
                      contentStyle={{
                        borderRadius: 10,
                        border: '1px solid hsl(var(--border))',
                        background: 'hsl(var(--popover))',
                        fontSize: 12,
                      }}
                      formatter={(value: number, name: string) => [eur(value), name]}
                    />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Bar dataKey="custo" name="Custo" fill="hsl(var(--muted-foreground))" radius={[4, 4, 0, 0]} opacity={0.35} />
                    <Bar dataKey="valor" name="Valor atual" fill={THEME_COLORS[0]} radius={[4, 4, 0, 0]}>
                      {chartData.map((entry, index) => (
                        <Cell key={entry.theme} fill={THEME_COLORS[index % THEME_COLORS.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="py-12 text-center text-sm text-muted-foreground">
                Ainda não há cópias na coleção.
              </p>
            )}
          </CardContent>
        </Card>

        <div className="space-y-4 lg:col-span-2">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Maiores valorizações</CardTitle>
            </CardHeader>
            <CardContent>
              {overview.top_gainers.length ? (
                <ul className="divide-y divide-border">
                  {overview.top_gainers.map((instance, index) => (
                    <MoverRow key={instance.id} instance={instance} rank={index + 1} />
                  ))}
                </ul>
              ) : (
                <p className="py-4 text-center text-sm text-muted-foreground">
                  Defina valores de mercado para ver esta lista.
                </p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Fora da coleção</CardTitle>
              <CardDescription>Reportado à parte, nunca misturado no ROI.</CardDescription>
            </CardHeader>
            <CardContent className="flex items-end justify-between">
              <div>
                <p className="numeric text-2xl font-semibold">{num(overview.departed_copies)}</p>
                <p className="text-xs text-muted-foreground">cópias vendidas ou oferecidas</p>
              </div>
              <div className="text-right">
                <p className="numeric text-lg font-medium">
                  {eur(overview.departed_sale_total_eur)}
                </p>
                <p className="text-xs text-muted-foreground">Σ valor de venda</p>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
