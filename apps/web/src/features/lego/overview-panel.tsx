import * as React from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip as RechartsTooltip,
  Treemap,
  XAxis,
  YAxis,
  ZAxis,
} from 'recharts';
import {
  AlertTriangle,
  Blocks,
  Boxes,
  Coins,
  Info,
  Layers,
  Percent,
  Tag,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';
import type { AcquisitionSource, LegoOverview, LegoSetInstance } from '@/lib/types';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/feedback';
import { Tooltip } from '@/components/ui/primitives';
import { eur, eurCompact, num, percent, relativeDays, signedEur } from '@/lib/format';
import { cn } from '@/lib/utils';
import { SOURCE_LABELS } from './constants';

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

function sourceLabel(source: string) {
  return SOURCE_LABELS[source as AcquisitionSource] ?? source;
}

/** «2026-03» → «mar 26», so the axis stays readable at a dozen points. */
function monthLabel(month: string) {
  const [year, index] = month.split('-');
  const name = new Date(Number(year), Number(index) - 1, 1).toLocaleDateString('pt-PT', {
    month: 'short',
  });
  return `${name} ${year.slice(2)}`;
}

function KpiCard({
  icon: Icon,
  label,
  value,
  secondary,
  hint,
  tooltip,
  tone = 'default',
  onClick,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: React.ReactNode;
  secondary?: React.ReactNode;
  hint?: React.ReactNode;
  tooltip?: React.ReactNode;
  tone?: 'default' | 'positive' | 'negative';
  onClick?: () => void;
}) {
  // A card without a destination is not a control, so it must not be a <button>.
  const Wrapper = onClick ? 'button' : 'div';
  return (
    <Wrapper
      {...(onClick ? { type: 'button' as const, onClick } : {})}
      className={cn(
        'flex flex-col items-start w-full rounded-xl border border-border bg-card p-4 text-left shadow-soft transition',
        onClick && 'cursor-pointer hover:-translate-y-0.5 hover:shadow-card',
      )}
    >
      <div className="flex items-center gap-1.5 text-muted-foreground">
        <Icon className="size-4" />
        <span className="text-xs font-medium uppercase tracking-wide">{label}</span>
        {tooltip ? (
          <Tooltip label={tooltip}>
            <Info className="size-3.5 cursor-help" />
          </Tooltip>
        ) : null}
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
      {secondary ? (
        <p
          className={cn(
            'numeric mt-0.5 text-sm font-medium',
            tone === 'positive' && 'text-success',
            tone === 'negative' && 'text-destructive',
            tone === 'default' && 'text-muted-foreground',
          )}
        >
          {secondary}
        </p>
      ) : null}
      {hint ? <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p> : null}
    </Wrapper>
  );
}

function SplitKpiCard({
  icon: Icon,
  label,
  leftValue,
  leftSecondary,
  leftHint,
  leftTone,
  rightValue,
  rightSecondary,
  rightHint,
  rightTone,
  tooltip,
  tone = 'default',
  onClick,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  leftValue: React.ReactNode;
  leftSecondary?: React.ReactNode;
  leftHint?: React.ReactNode;
  leftTone?: 'default' | 'positive' | 'negative';
  rightValue: React.ReactNode;
  rightSecondary?: React.ReactNode;
  rightHint?: React.ReactNode;
  rightTone?: 'default' | 'positive' | 'negative';
  tooltip?: React.ReactNode;
  tone?: 'default' | 'positive' | 'negative';
  onClick?: () => void;
}) {
  const Wrapper = onClick ? 'button' : 'div';
  const effectiveLeftTone = leftTone ?? tone;
  const effectiveRightTone = rightTone ?? tone;

  return (
    <Wrapper
      {...(onClick ? { type: 'button' as const, onClick } : {})}
      className={cn(
        'rounded-xl border border-border bg-card p-4 text-left shadow-soft transition',
        onClick && 'cursor-pointer hover:-translate-y-0.5 hover:shadow-card',
      )}
    >
      <div className="flex items-center gap-1.5 text-muted-foreground">
        <Icon className="size-4" />
        <span className="text-xs font-medium uppercase tracking-wide">{label}</span>
        {tooltip ? (
          <Tooltip label={tooltip}>
            <Info className="size-3.5 cursor-help" />
          </Tooltip>
        ) : null}
      </div>

      <div className="mt-2 grid grid-cols-2 divide-x divide-border">
        {/* Lado Esquerdo */}
        <div className="pr-3">
          <p
            className={cn(
              'numeric text-2xl font-semibold tracking-tight',
              effectiveLeftTone === 'positive' && 'text-success',
              effectiveLeftTone === 'negative' && 'text-destructive',
            )}
          >
            {leftValue}
          </p>
          {leftSecondary ? (
            <p
              className={cn(
                'numeric mt-0.5 text-sm font-medium',
                effectiveLeftTone === 'positive' && 'text-success',
                effectiveLeftTone === 'negative' && 'text-destructive',
                effectiveLeftTone === 'default' && 'text-muted-foreground',
              )}
            >
              {leftSecondary}
            </p>
          ) : null}
          {leftHint ? (
            <p className="mt-0.5 text-xs text-muted-foreground">{leftHint}</p>
          ) : null}
        </div>

        {/* Lado Direito */}
        <div className="pl-3">
          <p
            className={cn(
              'numeric text-2xl font-semibold tracking-tight',
              effectiveRightTone === 'positive' && 'text-success',
              effectiveRightTone === 'negative' && 'text-destructive',
            )}
          >
            {rightValue}
          </p>
          {rightSecondary ? (
            <p
              className={cn(
                'numeric mt-0.5 text-sm font-medium',
                effectiveRightTone === 'positive' && 'text-success',
                effectiveRightTone === 'negative' && 'text-destructive',
                effectiveRightTone === 'default' && 'text-muted-foreground',
              )}
            >
              {rightSecondary}
            </p>
          ) : null}
          {rightHint ? (
            <p className="mt-0.5 text-xs text-muted-foreground">{rightHint}</p>
          ) : null}
        </div>
      </div>
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
        <p
          className={cn(
            'numeric text-sm font-semibold',
            positive ? 'text-success' : 'text-destructive',
          )}
        >
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
  const chartData = overview.themes.map((theme) => ({
    theme: theme.theme,
    valor: Number(theme.value_eur),
    custo: Number(theme.cost_eur),
    copies: theme.copies,
    pvp: Number(theme.rrp_eur),
    sets: theme.unique_sets,
    pecas: theme.piece_count,
  }));
  const areaData = overview.areas.map((area) => ({
    area: area.area,
    sets: area.unique_sets,
    pvp: Number(area.rrp_eur),
    selado: area.sealed_copies,
    outro: area.copies - area.sealed_copies,
  }));
  const timelineData = overview.timeline.map((point) => ({
    month: monthLabel(point.month),
    copias: point.copies,
    custo: Number(point.cost_eur),
    valor: Number(point.value_eur),
  }));
  const retiredPct =
    overview.unique_sets > 0 ? (overview.retired_sets / overview.unique_sets) * 100 : 0;
  const retiredPctLabel = retiredPct.toLocaleString('pt-PT', {
    maximumFractionDigits: 1,
  });
  const paidToRrpRatio =
    Number(overview.total_rrp_eur) > 0 ? (Number(overview.total_cost_eur) / Number(overview.total_rrp_eur)) * 100 : 0;
  const paidToRrpRatioLabel = paidToRrpRatio.toLocaleString('pt-PT', {
    maximumFractionDigits: 1,
  });

  const topByPieces = [...overview.themes]
    .sort((a, b) => b.piece_count - a.piece_count)
    .slice(0, 8);
  const topByCount = [...overview.themes].sort((a, b) => b.unique_sets - a.unique_sets).slice(0, 8);
  const maxPieces = Math.max(1, ...topByPieces.map((t) => t.piece_count));
  const maxCount = Math.max(1, ...topByCount.map((t) => t.unique_sets));

  const treemapData = Object.values(
    overview.subthemes.reduce<Record<string, { name: string; children: { name: string; size: number }[] }>>(
      (acc, entry) => {
        const bucket = acc[entry.theme] ?? { name: entry.theme, children: [] };
        bucket.children.push({ name: entry.subtheme, size: Math.max(Number(entry.cost_eur), 0.01) });
        acc[entry.theme] = bucket;
        return acc;
      },
      {},
    ),
  );

  const releaseYearData = overview.release_years
    .filter((point) => point.year !== null)
    .map((point) => ({ year: String(point.year), conjuntos: point.unique_sets }));

  const eolData = [
    { name: 'Retirados', value: overview.retired_sets },
    { name: 'Em catálogo', value: Math.max(overview.unique_sets - overview.retired_sets, 0) },
  ];

  const channelData = overview.channels.map((channel) => ({
    source: sourceLabel(channel.source),
    custo: Number(channel.cost_eur),
    pvp: Number(channel.rrp_eur),
  }));

  const pppData = overview.piece_price_points.map((point) => ({
    x: point.piece_count,
    y: Number(point.cost_per_piece_eur),
    name: point.name,
    theme: point.theme,
  }));

  const totalBuildStateCopies = overview.build_states.reduce((sum, item) => sum + item.copies, 0);
  const disassembledCopies =
    overview.build_states.find((item) => item.build_state === 'DISASSEMBLED')?.copies ?? 0;
  const builtCopies = totalBuildStateCopies - disassembledCopies;
  const backlogPct =
    totalBuildStateCopies > 0 ? (disassembledCopies / totalBuildStateCopies) * 100 : 0; 
  const differentSetsPct =
    overview.copies_owned > 0 ? (overview.unique_sets / overview.copies_owned) * 100 : 0;
  const differentSetsPctLabel = differentSetsPct.toLocaleString('pt-PT', {
    maximumFractionDigits: 1,
  });
  const roi_pct_paid_value = Number(overview.total_value_eur) - Number(overview.total_rrp_eur);
  const roi_pct_paid =
    Number(overview.total_rrp_eur) > 0 ? (roi_pct_paid_value / Number(overview.total_rrp_eur)) * 100 : 0;
  const roi_pct_paidLabel = roi_pct_paid.toLocaleString('pt-PT', {
    maximumFractionDigits: 1,
  });

  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          icon={Coins}
          label="Custo total"
          value={eur(overview.total_rrp_eur)}
          hint={`${eur(overview.total_cost_eur)} [${paidToRrpRatioLabel} %] pago · ${overview.themes.length} temas`}
          onClick={() => onFilter({ tab: 'colecao'})}
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
          label="ROI (pvp)"
          value={signedEur(roi_pct_paid_value)}
          secondary={percent(String(roi_pct_paidLabel).replace(',', '.'))}
          tone={gainPositive ? 'positive' : 'negative'}
          tooltip="Valor atual − custo, só de conjuntos avaliados. Prendas e conjuntos sem valor definido ficam de fora."
        />
        <KpiCard
          icon={gainPositive ? TrendingUp : TrendingDown}
          label="ROI (custo)"
          value={signedEur(overview.unrealized_gain_eur)}
          secondary={percent(overview.roi_pct)}
          tone={gainPositive ? 'positive' : 'negative'}
          tooltip="Valor atual − custo, só de conjuntos avaliados. Prendas e conjuntos sem valor definido ficam de fora."
        />
        <KpiCard
          icon={Boxes}
          label="# Legos"
          value={num(overview.copies_owned)}
          hint={`${num(overview.unique_sets)} únicos · ${overview.themes.length} temas`}
          onClick={() => onFilter({ tab: 'colecao' })}
        />        
        <KpiCard
          icon={Layers}
          label="Peças"
          value={num(overview.total_pieces)}
          hint={`${num(overview.total_minifigs)} minifiguras`}
        />
        <KpiCard
          icon={AlertTriangle}
          label="Conjuntos retirados"
          value={num(overview.retired_sets)}
          secondary={overview.unique_sets > 0 ? `${retiredPctLabel} %` : undefined}
          onClick={() => onFilter({ tab: 'colecao', retirement: 'retired' })}
        />
        <KpiCard
          icon={Tag}
          label="Sets Fs"
          value={num(overview.fs_copies)}
          secondary={eur(overview.fs_rrp_eur)}
          onClick={
            overview.fs_copies > 0 ? () => onFilter({ tab: 'colecao', fs: '1' }) : undefined
          }
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

      <Card>
        <CardHeader>
          <CardTitle>Evolução da coleção</CardTitle>
          <CardDescription>
            Cópias e custo acumulados pela data de aquisição. A linha de valor é o valor{' '}
            <strong>de hoje</strong> de tudo o que já tinha em cada mês — não é uma cotação
            histórica, porque o módulo guarda um único valor por conjunto, por desenho.
            {overview.copies_without_date > 0
              ? ` ${overview.copies_without_date} cópia(s) sem data de aquisição ficam de fora.`
              : ''}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {timelineData.length > 1 ? (
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={timelineData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    vertical={false}
                    stroke="hsl(var(--border))"
                  />
                  <XAxis
                    dataKey="month"
                    tick={{ fontSize: 11 }}
                    stroke="hsl(var(--muted-foreground))"
                    minTickGap={16}
                  />
                  <YAxis
                    yAxisId="money"
                    tick={{ fontSize: 11 }}
                    stroke="hsl(var(--muted-foreground))"
                    tickFormatter={(value: number) => eurCompact(value)}
                    width={62}
                  />
                  <YAxis
                    yAxisId="copies"
                    orientation="right"
                    tick={{ fontSize: 11 }}
                    stroke="hsl(var(--muted-foreground))"
                    width={40}
                  />
                  <RechartsTooltip
                    contentStyle={{
                      borderRadius: 10,
                      border: '1px solid hsl(var(--border))',
                      background: 'hsl(var(--popover))',
                      fontSize: 12,
                    }}
                    formatter={(value: number, name: string) => [
                      name === 'Cópias' ? num(value) : eur(value),
                      name,
                    ]}
                  />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Line
                    yAxisId="money"
                    type="monotone"
                    dataKey="custo"
                    name="Custo acumulado"
                    stroke="hsl(var(--muted-foreground))"
                    strokeWidth={2}
                    dot={false}
                  />
                  <Line
                    yAxisId="money"
                    type="monotone"
                    dataKey="valor"
                    name="Valor atual acumulado"
                    stroke={THEME_COLORS[0]}
                    strokeWidth={2}
                    strokeDasharray="5 3"
                    dot={false}
                  />
                  <Line
                    yAxisId="copies"
                    type="monotone"
                    dataKey="copias"
                    name="Cópias"
                    stroke={THEME_COLORS[1]}
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="py-12 text-center text-sm text-muted-foreground">
              Registe datas de aquisição em pelo menos dois meses para ver a evolução.
            </p>
          )}
        </CardContent>
      </Card>

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
              <div className="h-72 overflow-x-auto">
                <div
                  style={{ minWidth: `${Math.max(chartData.length * 70, 600)}px`, height: '100%' }}
                >
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
                      <CartesianGrid
                        strokeDasharray="3 3"
                        vertical={false}
                        stroke="hsl(var(--border))"
                      />
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
                        yAxisId="money"
                        tick={{ fontSize: 11 }}
                        stroke="hsl(var(--muted-foreground))"
                        tickFormatter={(value: number) => eurCompact(value)}
                        width={62}
                      />
                      <YAxis
                        yAxisId="sets"
                        orientation="right"
                        tick={{ fontSize: 11 }}
                        stroke="hsl(var(--muted-foreground))"
                        width={36}
                        allowDecimals={false}
                      />
                      <RechartsTooltip
                        contentStyle={{
                          borderRadius: 10,
                          border: '1px solid hsl(var(--border))',
                          background: 'hsl(var(--popover))',
                          fontSize: 12,
                        }}
                        formatter={(value: number, name: string) => [
                          name === 'Nº de conjuntos' ? num(value) : eur(value),
                          name,
                        ]}
                      />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                      <Bar
                        yAxisId="money"
                        dataKey="pvp"
                        name="PVP"
                        fill={THEME_COLORS[1]}
                        radius={[4, 4, 0, 0]}
                        opacity={0.35}
                      />
                      <Bar
                        yAxisId="money"
                        dataKey="custo"
                        name="Custo"
                        fill="hsl(var(--muted-foreground))"
                        radius={[4, 4, 0, 0]}
                        opacity={0.35}
                      />
                      <Bar yAxisId="money" dataKey="valor" name="Valor atual" radius={[4, 4, 0, 0]}>
                        {chartData.map((entry, index) => (
                          <Cell
                            key={entry.theme}
                            fill={THEME_COLORS[index % THEME_COLORS.length]}
                          />
                        ))}
                      </Bar>
                      <Line
                        yAxisId="sets"
                        type="monotone"
                        dataKey="sets"
                        name="Nº de conjuntos"
                        stroke="hsl(var(--foreground))"
                        strokeWidth={2}
                        dot={{ r: 3 }}
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
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

      <Card>
        <CardHeader>
          <CardTitle>Distribuição por área</CardTitle>
          <CardDescription>
            Número de conjuntos e PVP acumulado por local de arrumação.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {areaData.length ? (
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={areaData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" />
                  <XAxis
                    dataKey="area"
                    tick={{ fontSize: 11 }}
                    stroke="hsl(var(--muted-foreground))"
                    interval={0}
                    angle={-18}
                    textAnchor="end"
                    height={54}
                  />
                  <YAxis
                    yAxisId="sets"
                    tick={{ fontSize: 11 }}
                    stroke="hsl(var(--muted-foreground))"
                    width={36}
                    allowDecimals={false}
                  />
                  <YAxis
                    yAxisId="money"
                    orientation="right"
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
                    formatter={(value: number, name: string) => [
                      name === 'PVP' ? eur(value) : num(value),
                      name,
                    ]}
                  />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar yAxisId="sets" dataKey="sets" name="Conjuntos" fill={THEME_COLORS[0]} radius={[4, 4, 0, 0]} />
                  <Bar yAxisId="money" dataKey="pvp" name="PVP" fill={THEME_COLORS[1]} radius={[4, 4, 0, 0]} opacity={0.6} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="py-12 text-center text-sm text-muted-foreground">
              Sem cópias arrumadas.
            </p>
          )}
        </CardContent>
      </Card>

      <div className="space-y-2">
        <h3 className="text-sm font-semibold text-muted-foreground">
          Gráficos candidatos — a escolher o que fica
        </h3>
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Top temas: nº de conjuntos vs. peças</CardTitle>
              <CardDescription>
                Quem lidera em número de caixas nem sempre lidera em volume de peças.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
              <div>
                <p className="mb-2 text-xs font-medium text-muted-foreground">Por nº de conjuntos</p>
                <ul className="space-y-1.5">
                  {topByCount.map((theme) => (
                    <li key={theme.theme} className="text-xs">
                      <div className="flex items-center justify-between">
                        <span className="truncate">{theme.theme}</span>
                        <span className="numeric shrink-0 font-medium">{theme.unique_sets}</span>
                      </div>
                      <div className="h-1.5 rounded-full bg-muted">
                        <div
                          className="h-full rounded-full bg-[color:var(--bar)]"
                          style={{
                            width: `${(theme.unique_sets / maxCount) * 100}%`,
                            ['--bar' as string]: THEME_COLORS[0],
                          }}
                        />
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <p className="mb-2 text-xs font-medium text-muted-foreground">Por nº de peças</p>
                <ul className="space-y-1.5">
                  {topByPieces.map((theme) => (
                    <li key={theme.theme} className="text-xs">
                      <div className="flex items-center justify-between">
                        <span className="truncate">{theme.theme}</span>
                        <span className="numeric shrink-0 font-medium">
                          {num(theme.piece_count)}
                        </span>
                      </div>
                      <div className="h-1.5 rounded-full bg-muted">
                        <div
                          className="h-full rounded-full bg-[color:var(--bar)]"
                          style={{
                            width: `${(theme.piece_count / maxPieces) * 100}%`,
                            ['--bar' as string]: THEME_COLORS[1],
                          }}
                        />
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Temas e subtemas por custo</CardTitle>
              <CardDescription>Treemap ponderado pelo custo pago.</CardDescription>
            </CardHeader>
            <CardContent>
              {treemapData.length ? (
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <Treemap
                      data={treemapData}
                      dataKey="size"
                      nameKey="name"
                      stroke="hsl(var(--card))"
                      fill={THEME_COLORS[0]}
                    >
                      <RechartsTooltip
                        contentStyle={{
                          borderRadius: 10,
                          border: '1px solid hsl(var(--border))',
                          background: 'hsl(var(--popover))',
                          fontSize: 12,
                        }}
                        formatter={(value: number) => eur(value)}
                      />
                    </Treemap>
                  </ResponsiveContainer>
                </div>
              ) : (
                <p className="py-12 text-center text-sm text-muted-foreground">Sem dados.</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Anos de lançamento</CardTitle>
              <CardDescription>Nostálgico vs. moderno — a curva bimodal da coleção.</CardDescription>
            </CardHeader>
            <CardContent>
              {releaseYearData.length ? (
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={releaseYearData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" />
                      <XAxis
                        dataKey="year"
                        tick={{ fontSize: 10 }}
                        stroke="hsl(var(--muted-foreground))"
                        interval={0}
                        angle={-45}
                        textAnchor="end"
                        height={50}
                      />
                      <YAxis
                        tick={{ fontSize: 11 }}
                        stroke="hsl(var(--muted-foreground))"
                        allowDecimals={false}
                        width={32}
                      />
                      <RechartsTooltip
                        contentStyle={{
                          borderRadius: 10,
                          border: '1px solid hsl(var(--border))',
                          background: 'hsl(var(--popover))',
                          fontSize: 12,
                        }}
                        formatter={(value: number) => [num(value), 'Conjuntos']}
                      />
                      <Bar dataKey="conjuntos" name="Conjuntos" fill={THEME_COLORS[0]} radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <p className="py-12 text-center text-sm text-muted-foreground">
                  Sem datas de lançamento.
                </p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Retirados vs. em catálogo</CardTitle>
              <CardDescription>Proporção de EOL sobre os conjuntos únicos.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={eolData}
                      dataKey="value"
                      nameKey="name"
                      innerRadius={55}
                      outerRadius={85}
                      paddingAngle={2}
                    >
                      <Cell fill="hsl(var(--warning))" />
                      <Cell fill={THEME_COLORS[0]} />
                    </Pie>
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <RechartsTooltip
                      contentStyle={{
                        borderRadius: 10,
                        border: '1px solid hsl(var(--border))',
                        background: 'hsl(var(--popover))',
                        fontSize: 12,
                      }}
                      formatter={(value: number) => num(value)}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Custo real vs. PVP por canal</CardTitle>
              <CardDescription>Onde o cartão/campanhas alargam mais a diferença.</CardDescription>
            </CardHeader>
            <CardContent>
              {channelData.length ? (
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={channelData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" />
                      <XAxis
                        dataKey="source"
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
                      <Bar dataKey="custo" name="Custo real" fill="hsl(var(--muted-foreground))" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="pvp" name="PVP" fill={THEME_COLORS[1]} radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <p className="py-12 text-center text-sm text-muted-foreground">Sem dados.</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Preço por peça</CardTitle>
              <CardDescription>Peças vs. custo efetivo por peça, cópia a cópia.</CardDescription>
            </CardHeader>
            <CardContent>
              {pppData.length ? (
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <ScatterChart margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                      <XAxis
                        type="number"
                        dataKey="x"
                        name="Peças"
                        tick={{ fontSize: 11 }}
                        stroke="hsl(var(--muted-foreground))"
                      />
                      <YAxis
                        type="number"
                        dataKey="y"
                        name="€/peça"
                        tick={{ fontSize: 11 }}
                        stroke="hsl(var(--muted-foreground))"
                        width={48}
                      />
                      <ZAxis range={[40, 40]} />
                      <RechartsTooltip
                        cursor={{ strokeDasharray: '3 3' }}
                        contentStyle={{
                          borderRadius: 10,
                          border: '1px solid hsl(var(--border))',
                          background: 'hsl(var(--popover))',
                          fontSize: 12,
                        }}
                        formatter={(value: number, name: string) => [
                          name === 'Peças' ? num(value) : eur(value),
                          name,
                        ]}
                        labelFormatter={() => ''}
                      />
                      <Scatter data={pppData} fill={THEME_COLORS[0]} opacity={0.7} />
                    </ScatterChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <p className="py-12 text-center text-sm text-muted-foreground">Sem dados.</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Selados vs. abertos por área</CardTitle>
              <CardDescription>Localização física do acervo, por estado de embalagem.</CardDescription>
            </CardHeader>
            <CardContent>
              {areaData.length ? (
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={areaData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" />
                      <XAxis
                        dataKey="area"
                        tick={{ fontSize: 11 }}
                        stroke="hsl(var(--muted-foreground))"
                        interval={0}
                        angle={-18}
                        textAnchor="end"
                        height={54}
                      />
                      <YAxis tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" allowDecimals={false} width={32} />
                      <RechartsTooltip
                        contentStyle={{
                          borderRadius: 10,
                          border: '1px solid hsl(var(--border))',
                          background: 'hsl(var(--popover))',
                          fontSize: 12,
                        }}
                        formatter={(value: number, name: string) => [num(value), name]}
                      />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                      <Bar dataKey="selado" name="Selado" stackId="cond" fill={THEME_COLORS[0]} />
                      <Bar dataKey="outro" name="Aberto/montado" stackId="cond" fill="hsl(var(--muted-foreground))" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <p className="py-12 text-center text-sm text-muted-foreground">Sem dados.</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Backlog de construção</CardTitle>
              <CardDescription>Proporção de cópias ainda por montar.</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="numeric text-3xl font-semibold">
                {backlogPct.toLocaleString('pt-PT', { maximumFractionDigits: 1 })} %
              </p>
              <div className="mt-3 h-3 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-warning"
                  style={{ width: `${backlogPct}%` }}
                />
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                {num(disassembledCopies)} desmontados vs. {num(builtCopies)} montados
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
