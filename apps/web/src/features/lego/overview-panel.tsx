import * as React from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Customized,
  LabelList,
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
  // Blocks,
  Boxes,
  Coins,
  Info,
  Layers,
  // Percent,
  Tag,
  TrendingDown,
  TrendingUp,
  ChevronLeft,
  ChevronRight
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

// function SplitKpiCard({
//   icon: Icon,
//   label,
//   leftValue,
//   leftSecondary,
//   leftHint,
//   leftTone,
//   rightValue,
//   rightSecondary,
//   rightHint,
//   rightTone,
//   tooltip,
//   tone = 'default',
//   onClick,
// }: {
//   icon: React.ComponentType<{ className?: string }>;
//   label: string;
//   leftValue: React.ReactNode;
//   leftSecondary?: React.ReactNode;
//   leftHint?: React.ReactNode;
//   leftTone?: 'default' | 'positive' | 'negative';
//   rightValue: React.ReactNode;
//   rightSecondary?: React.ReactNode;
//   rightHint?: React.ReactNode;
//   rightTone?: 'default' | 'positive' | 'negative';
//   tooltip?: React.ReactNode;
//   tone?: 'default' | 'positive' | 'negative';
//   onClick?: () => void;
// }) {
//   const Wrapper = onClick ? 'button' : 'div';
//   const effectiveLeftTone = leftTone ?? tone;
//   const effectiveRightTone = rightTone ?? tone;

//   return (
//     <Wrapper
//       {...(onClick ? { type: 'button' as const, onClick } : {})}
//       className={cn(
//         'rounded-xl border border-border bg-card p-4 text-left shadow-soft transition',
//         onClick && 'cursor-pointer hover:-translate-y-0.5 hover:shadow-card',
//       )}
//     >
//       <div className="flex items-center gap-1.5 text-muted-foreground">
//         <Icon className="size-4" />
//         <span className="text-xs font-medium uppercase tracking-wide">{label}</span>
//         {tooltip ? (
//           <Tooltip label={tooltip}>
//             <Info className="size-3.5 cursor-help" />
//           </Tooltip>
//         ) : null}
//       </div>

//       <div className="mt-2 grid grid-cols-2 divide-x divide-border">
//         {/* Lado Esquerdo */}
//         <div className="pr-3">
//           <p
//             className={cn(
//               'numeric text-2xl font-semibold tracking-tight',
//               effectiveLeftTone === 'positive' && 'text-success',
//               effectiveLeftTone === 'negative' && 'text-destructive',
//             )}
//           >
//             {leftValue}
//           </p>
//           {leftSecondary ? (
//             <p
//               className={cn(
//                 'numeric mt-0.5 text-sm font-medium',
//                 effectiveLeftTone === 'positive' && 'text-success',
//                 effectiveLeftTone === 'negative' && 'text-destructive',
//                 effectiveLeftTone === 'default' && 'text-muted-foreground',
//               )}
//             >
//               {leftSecondary}
//             </p>
//           ) : null}
//           {leftHint ? <p className="mt-0.5 text-xs text-muted-foreground">{leftHint}</p> : null}
//         </div>

//         {/* Lado Direito */}
//         <div className="pl-3">
//           <p
//             className={cn(
//               'numeric text-2xl font-semibold tracking-tight',
//               effectiveRightTone === 'positive' && 'text-success',
//               effectiveRightTone === 'negative' && 'text-destructive',
//             )}
//           >
//             {rightValue}
//           </p>
//           {rightSecondary ? (
//             <p
//               className={cn(
//                 'numeric mt-0.5 text-sm font-medium',
//                 effectiveRightTone === 'positive' && 'text-success',
//                 effectiveRightTone === 'negative' && 'text-destructive',
//                 effectiveRightTone === 'default' && 'text-muted-foreground',
//               )}
//             >
//               {rightSecondary}
//             </p>
//           ) : null}
//           {rightHint ? <p className="mt-0.5 text-xs text-muted-foreground">{rightHint}</p> : null}
//         </div>
//       </div>
//     </Wrapper>
//   );
// }

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
  const chartData = overview.themes
    .map((theme) => ({
      theme: theme.theme,
      valor: Number(theme.value_eur),
      custo: Number(theme.cost_eur),
      copies: theme.copies,
      pvp: Number(theme.rrp_eur),
      sets: theme.unique_sets,
      pecas: theme.piece_count,
    }))
    .sort((a, b) => b.valor - a.valor);
  const areaData = overview.areas.map((area) => ({
    area: area.area,
    sets: area.unique_sets,
    pvp: Number(area.rrp_eur),
  }));
  /** "Sem local" is a synthetic bucket for copies with no storage location — there is
   * no matching `storage_area` value to filter by, so that slice is not clickable. */
  function handleAreaClick(area: string | undefined) {
    if (!area || area === 'Sem local') return;
    onFilter({ tab: 'colecao', storage_area: area });
  }
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
    Number(overview.total_rrp_eur) > 0
      ? (Number(overview.total_cost_eur) / Number(overview.total_rrp_eur)) * 100
      : 0;
  const paidToRrpRatioLabel = paidToRrpRatio.toLocaleString('pt-PT', {
    maximumFractionDigits: 1,
  });
  const topByPieces = [...overview.themes]
    .sort((a, b) => b.piece_count - a.piece_count)
    .slice(0, 8);
  const topByCount = [...overview.themes].sort((a, b) => b.unique_sets - a.unique_sets).slice(0, 8);
  const maxPieces = Math.max(1, ...topByPieces.map((t) => t.piece_count));
  const maxCount = Math.max(1, ...topByCount.map((t) => t.unique_sets));
  /** One box per theme, sized by PVP — subtemas only surface in the tooltip
   * (as a sum-of-money breakdown), so the treemap stays a flat single level
   * instead of nesting a nearly-empty rectangle per (theme, subtema) leaf. */
  const treemapData = Object.values(
    overview.subthemes.reduce<
      Record<string, { name: string; size: number; subthemes: { name: string; rrp: number }[] }>
    >((acc, entry) => {
      const bucket = acc[entry.theme] ?? { name: entry.theme, size: 0, subthemes: [] };
      const rrp = Number(entry.rrp_eur);
      bucket.size += rrp;
      bucket.subthemes.push({ name: entry.subtheme, rrp });
      acc[entry.theme] = bucket;
      return acc;
    }, {}),
  )
    .map((bucket) => ({
      ...bucket,
      size: Math.max(bucket.size, 0.01),
      subthemes: bucket.subthemes.sort((a, b) => b.rrp - a.rrp),
    }))
    .sort((a, b) => b.size - a.size);
  const eolData = [
    { name: 'Retirados', value: overview.retired_sets },
    { name: 'Em catálogo', value: Math.max(overview.unique_sets - overview.retired_sets, 0) },
  ];

  const channelData = overview.channels.map((channel) => ({
    source: sourceLabel(channel.source),
    custo: Number(channel.cost_eur),
    pvp: Number(channel.rrp_eur),
  }));

  const pppCostData = overview.piece_price_points.map((point) => ({
    x: point.piece_count,
    y: Number(point.cost_per_piece_eur),
    name: point.name,
    setNumber: point.set_number,
    theme: point.theme,
  }));
  const pppRrpData = overview.piece_price_points
    .filter((point) => point.rrp_per_piece_eur !== null && point.rrp_per_piece_eur !== undefined)
    .map((point) => ({
      x: point.piece_count,
      y: Number(point.rrp_per_piece_eur),
      name: point.name,
      setNumber: point.set_number,
      theme: point.theme,
    }));

  const yearPieceData = overview.release_year_points.map((point) => ({
    year: point.year,
    pieces: point.piece_count,
    name: point.name,
    setNumber: point.set_number,
    theme: point.theme,
  }));
  /** Least-squares fit of pieces = a + b·ln(year − minYear + 1), sampled into a smooth curve. */
  const yearPieceTrend = (() => {
    if (yearPieceData.length < 2) return [];
    const minYear = Math.min(...yearPieceData.map((point) => point.year));
    const maxYear = Math.max(...yearPieceData.map((point) => point.year));
    if (maxYear === minYear) return [];
    const xs = yearPieceData.map((point) => Math.log(point.year - minYear + 1));
    const ys = yearPieceData.map((point) => point.pieces);
    const n = xs.length;
    const xMean = xs.reduce((sum, x) => sum + x, 0) / n;
    const yMean = ys.reduce((sum, y) => sum + y, 0) / n;
    let covariance = 0;
    let variance = 0;
    xs.forEach((x, index) => {
      covariance += (x - xMean) * (ys[index] - yMean);
      variance += (x - xMean) ** 2;
    });
    const slope = variance !== 0 ? covariance / variance : 0;
    const intercept = yMean - slope * xMean;
    const steps = 30;
    return Array.from({ length: steps + 1 }, (_, index) => {
      const year = minYear + ((maxYear - minYear) * index) / steps;
      return {
        year: Math.round(year * 10) / 10,
        pieces: Math.max(0, intercept + slope * Math.log(year - minYear + 1)),
      };
    });
  })();

  const pieceBracketData = overview.piece_brackets.map((bracket) => ({
    bracket: bracket.bracket,
    sets: bracket.unique_sets,
  }));
  const totalBracketSets = pieceBracketData.reduce((sum, bracket) => sum + bracket.sets, 0);

  const totalBuildStateCopies = overview.build_states.reduce((sum, item) => sum + item.copies, 0);
  const disassembledCopies =
    overview.build_states.find((item) => item.build_state === 'DISASSEMBLED')?.copies ?? 0;
  const builtCopies = totalBuildStateCopies - disassembledCopies;
  const backlogPct =
    totalBuildStateCopies > 0 ? (disassembledCopies / totalBuildStateCopies) * 100 : 0;
  
  const roi_pct_paid_value = Number(overview.total_value_eur) - Number(overview.total_rrp_eur);
  const roi_pct_paid =
    Number(overview.total_rrp_eur) > 0
      ? (roi_pct_paid_value / Number(overview.total_rrp_eur)) * 100
      : 0;
  const pct_fs =
    Number(overview.fs_copies) > 0
      ? (Number(overview.fs_copies) / Number(overview.copies_owned)) * 100
      : 0;      
  const roi_pct_paidLabel = roi_pct_paid.toLocaleString('pt-PT', {
    maximumFractionDigits: 1,
  });

  // 1. Agrupa os temas de cada ano a partir de release_year_points
  const releaseYearData = React.useMemo(() => {
    const yearMap = new Map<string, Record<string, any>>();
    overview.release_year_points.forEach((point) => {
      if (point.year === null || point.year === undefined) return;
      const yearKey = String(point.year);
      const theme = point.theme || 'Outros';

      if (!yearMap.has(yearKey)) {
        yearMap.set(yearKey, { year: yearKey });
      }

      const row = yearMap.get(yearKey)!;
      row[theme] = (row[theme] || 0) + 1;
    });
    return Array.from(yearMap.values()).sort((a, b) => Number(a.year) - Number(b.year));
  }, [overview.release_year_points]);

  // 2. Extrai a lista de temas presentes nas barras
  const releaseYearThemes = React.useMemo(() => {
    const themeSet = new Set<string>();
    releaseYearData.forEach((row) => {
      Object.keys(row).forEach((k) => {
        if (k !== 'year') themeSet.add(k);
      });
    });
    return Array.from(themeSet);
  }, [releaseYearData]);

  const releaseYearDataWithTotals = releaseYearData.map((d) => ({
    ...d,
    total: releaseYearThemes.reduce((sum, theme) => sum + (Number(d[theme]) || 0), 0),
  }));  

  const themesScrollRef = React.useRef<HTMLDivElement>(null);

  const scrollThemes = (direction: 'left' | 'right') => {
    if (themesScrollRef.current) {
      const scrollAmount = 140;
      themesScrollRef.current.scrollBy({
        left: direction === 'left' ? -scrollAmount : scrollAmount,
        behavior: 'smooth',
      });
    }
  };

  const areaLegendScrollRef = React.useRef<HTMLDivElement>(null);

  const scrollAreaLegend = (direction: 'left' | 'right') => {
    if (areaLegendScrollRef.current) {
      const scrollAmount = 140;
      areaLegendScrollRef.current.scrollBy({
        left: direction === 'left' ? -scrollAmount : scrollAmount,
        behavior: 'smooth',
      });
    }
  };


  /** Theme name plus sets/pieces underneath, agora totalmente clicável */
  function ThemeAxisTick({
    x,
    y,
    payload,
  }: {
    x: number;
    y: number;
    payload: { value: string };
  }) {
    const entry = chartData.find((item) => item.theme === payload.value);

    return (
      <g
        transform={`translate(${x},${y})`}
        className="cursor-pointer group select-none"
        onClick={() => onFilter({ tab: 'colecao', theme: payload.value })}
      >
        {/* Nome do tema com hover highlight */}
        <text
          x={-8}
          y={-2}
          textAnchor="end"
          fontSize={12}
          fontWeight={500}
          fill="hsl(var(--foreground))"
          className="transition-colors group-hover:fill-primary"
        >
          {payload.value}
        </text>

        {/* Subtítulo: nº de sets e peças */}
        <text
          x={-8}
          y={12}
          textAnchor="end"
          fontSize={11}
          fill="hsl(var(--muted-foreground))"
          className="transition-colors group-hover:fill-primary/80"
        >
          {entry ? `${entry.sets} sets · ${num(entry.pecas)} pçs` : ''}
        </text>
      </g>
    );
  }

  /** Custom treemap cell: colored by theme index, labelled only when there's room,
   * clickable straight through to the filtered collection. */
  function renderTreemapNode(props: {
    x: number;
    y: number;
    width: number;
    height: number;
    index: number;
    name: string;
    size: number;
  }) {
    const { x, y, width, height, index, name, size } = props;
    const canLabel = width > 56 && height > 28;
    return (
      <g
        onClick={() => onFilter({ tab: 'colecao', theme: name })}
        style={{ cursor: 'pointer' }}
      >
        <rect
          x={x}
          y={y}
          width={width}
          height={height}
          rx={4}
          fill={THEME_COLORS[index % THEME_COLORS.length]}
          fillOpacity={0.85}
          stroke="hsl(var(--card))"
          strokeWidth={2}
        />
        {canLabel ? (
          <text x={x + 8} y={y + 18} fontSize={12} fontWeight={600} fill="#fff">
            {name}
          </text>
        ) : null}
        {canLabel ? (
          <text x={x + 8} y={y + 33} fontSize={10} fill="rgba(255,255,255,0.85)">
            {eurCompact(size)}
          </text>
        ) : null}
      </g>
    );
  }

  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          icon={Coins}
          label="Custo total"
          value={eur(overview.total_rrp_eur)}
          hint={`${eur(overview.total_cost_eur)} [${paidToRrpRatioLabel} %] pago · ${overview.themes.length} temas`}
          onClick={() => onFilter({ tab: 'colecao' })}
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
          hint={overview.unique_sets > 0 ? `${retiredPctLabel} %` : undefined}
          onClick={() => onFilter({ tab: 'colecao', retirement: 'retired' })}
        />
        <KpiCard
          icon={Tag}
          label="Sets Fs"
          value={num(overview.fs_copies)}
          hint={`${eur(overview.fs_rrp_eur)}  · ${percent(pct_fs)}`}
          onClick={overview.fs_copies > 0 ? () => onFilter({ tab: 'colecao', fs: '1' }) : undefined}
        />
      </div>

      {/* Message warning real value updated */}
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

      {/* GRAFICO: Evolução Coleção */}
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
      {/* FIM GRAFICO: Evolução Coleção */}

      {/* GRAFICO: Valor e Cópias por tema + SIDE GRAPHS */}
      <div className="grid gap-4 lg:grid-cols-5 items-start">
        <Card className="lg:col-span-3">
          <CardHeader>
            <CardTitle>Valor e cópias por tema</CardTitle>
            <CardDescription>
              Apenas cópias na coleção. Vendidos e oferecidos ficam fora, por desenho. Clica numa
              barra ou no nome do tema à esquerda para ver os conjuntos desse tema.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {chartData.length ? (
              <div className="max-h-[580px] overflow-y-auto pr-2">
                {/* Aumenta a altura proporcional para dar espaço às 3 barras por categoria */}
                <div style={{ height: `${Math.max(chartData.length * 64, 340)}px` }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart
                      data={chartData}
                      layout="vertical"
                      barGap={2}
                      barCategoryGap={12}
                      /* Margem direita aumentada (ex.: 54px) para os rótulos não cortarem */
                      margin={{ top: 16, right: 54, left: 8, bottom: 4 }}
                    >
                      <CartesianGrid
                        strokeDasharray="3 3"
                        horizontal={false}
                        stroke="hsl(var(--border))"
                      />

                      {/* Eixo dos Valores monetários (fundo) */}
                      <XAxis
                        xAxisId="euros"
                        type="number"
                        tick={{ fontSize: 11 }}
                        stroke="hsl(var(--muted-foreground))"
                        tickFormatter={(value: number) => eurCompact(value)}
                      />

                      {/* Eixo da Contagem de Sets (topo) */}
                      <XAxis
                        xAxisId="sets"
                        type="number"
                        orientation="top"
                        stroke="hsl(var(--primary))"
                        tick={{ fontSize: 11 }}
                        allowDecimals={false}
                        tickFormatter={(value: number) => `${value} sets`}
                      />

                      <YAxis
                        type="category"
                        dataKey="theme"
                        tick={ThemeAxisTick as never}
                        stroke="hsl(var(--border))"
                        width={124}
                      />

                      <RechartsTooltip
                        contentStyle={{
                          borderRadius: 10,
                          border: '1px solid hsl(var(--border))',
                          background: 'hsl(var(--popover))',
                          fontSize: 12,
                        }}
                        formatter={(value: number, name: string) => [
                          name === 'Conjuntos' ? value : eur(value),
                          name,
                        ]}
                        labelFormatter={(label, item) => {
                          const entry = item?.[0]?.payload;
                          return entry
                            ? `${label} · ${entry.sets} sets · ${num(entry.pecas)} peças`
                            : label;
                        }}
                      />

                      <Legend wrapperStyle={{ fontSize: 12, paddingTop: 6 }} />

                      {/* Barra 1: Preço pago */}
                      <Bar
                        xAxisId="euros"
                        dataKey="custo"
                        name="Preço pago"
                        fill="hsl(var(--warning))"
                        radius={[0, 4, 4, 0]}
                        opacity={0.8}
                        barSize={14}
                        cursor="pointer"
                        onClick={(entry) => onFilter({ tab: 'colecao', theme: entry.theme })}
                      >
                        <LabelList
                          dataKey="custo"
                          position="right"
                          formatter={(v: number) => (v > 0 ? eurCompact(v) : '')}
                          fill="hsl(var(--muted-foreground))"
                          fontSize={10}
                          offset={6}
                        />
                      </Bar>

                      {/* Barra 2: PVP */}
                      <Bar
                        xAxisId="euros"
                        dataKey="pvp"
                        name="PVP"
                        fill="hsl(var(--muted-foreground))"
                        radius={[0, 4, 4, 0]}
                        opacity={0.35}
                        barSize={14}
                        cursor="pointer"
                        onClick={(entry) => onFilter({ tab: 'colecao', theme: entry.theme })}
                      >
                        <LabelList
                          dataKey="pvp"
                          position="right"
                          formatter={(v: number) => (v > 0 ? eurCompact(v) : '')}
                          fill="hsl(var(--muted-foreground))"
                          fontSize={10}
                          offset={6}
                        />
                      </Bar>

                      {/* Barra 3: Valor atual */}
                      <Bar
                        xAxisId="euros"
                        dataKey="valor"
                        name="Valor atual"
                        fill="hsl(var(--success))"
                        radius={[0, 4, 4, 0]}
                        opacity={0.8}
                        barSize={14}
                        cursor="pointer"
                        onClick={(entry) => onFilter({ tab: 'colecao', theme: entry.theme })}
                      >
                        <LabelList
                          dataKey="valor"
                          position="right"
                          formatter={(v: number) => (v > 0 ? eurCompact(v) : '')}
                          fill="hsl(var(--foreground))"
                          fontSize={10}
                          fontWeight={600}
                          offset={6}
                        />
                      </Bar>

                      {/* Linha: Sets */}
                      <Line
                        xAxisId="sets"
                        type="monotone"
                        dataKey="sets"
                        name="Conjuntos"
                        stroke="hsl(var(--primary))"
                        strokeWidth={2.5}
                        dot={{ r: 4 }}
                        activeDot={{ r: 6 }}
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

        {/* Side Graphs */}
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

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Fora da coleção</CardTitle>
              <CardDescription>Reportado à parte, não misturado no ROI.</CardDescription>
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
      {/* FIM: Valor e Cópias por tema + SIDE GRAPHS */}

      {/* Series 2 Graficos*/}
      <div className="grid gap-4 lg:grid-cols-2">
        
        {/* Anel distribuicao localização */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle>Distribuição por localização (Anel Duplo)</CardTitle>
            <CardDescription>
              Anel interior: PVP total · Anel exterior: Sets · clica numa área para filtrar.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {areaData.length ? (
              <div className="flex flex-col sm:flex-row items-center gap-2 sm:gap-4 h-[230px] w-full">
                {/* Gráfico Donut Duplo */}
                <div className="h-full w-full sm:w-[62%] min-w-0">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart margin={{ top: 10, right: 10, bottom: 10, left: 10 }}>
                      <RechartsTooltip
                        contentStyle={{
                          borderRadius: 10,
                          border: '1px solid hsl(var(--border))',
                          background: 'hsl(var(--popover))',
                          fontSize: 12,
                        }}
                        formatter={(value: number, name: string, item: any) => {
                          const isPvp = item?.payload?.pvp === value;
                          return [
                            isPvp ? eur(value) : `${num(value)} conjuntos`,
                            isPvp ? 'PVP' : 'Conjuntos',
                          ];
                        }}
                      />

                      {/* Indicadores no centro do donut */}
                      <text
                        x="50%"
                        y="46%"
                        textAnchor="middle"
                        dominantBaseline="middle"
                        className="fill-muted-foreground text-[10px] font-medium tracking-wider uppercase"
                      >
                        Int: PVP
                      </text>
                      <text
                        x="50%"
                        y="54%"
                        textAnchor="middle"
                        dominantBaseline="middle"
                        className="fill-foreground text-[11px] font-semibold tracking-wider uppercase"
                      >
                        Ext: Sets
                      </text>

                      {/* Anel Interior: PVP */}
                      <Pie
                        data={areaData}
                        dataKey="pvp"
                        nameKey="area"
                        cx="50%"
                        cy="50%"
                        innerRadius={45}
                        outerRadius={72}
                        paddingAngle={2}
                        cursor="pointer"
                        onClick={(entry) => handleAreaClick(entry.area)}
                        label={({ cx, cy, midAngle, innerRadius, outerRadius, percent, value }) => {
                          if (percent < 0.1) return null;
                          const RADIAN = Math.PI / 180;
                          const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
                          const x = cx + radius * Math.cos(-midAngle * RADIAN);
                          const y = cy + radius * Math.sin(-midAngle * RADIAN);

                          return (
                            <text
                              x={x}
                              y={y}
                              fill="#ffffff"
                              textAnchor="middle"
                              dominantBaseline="central"
                              fontSize={9}
                              fontWeight={600}
                            >
                              {eur(value)}
                            </text>
                          );
                        }}
                        labelLine={false}
                      >
                        {areaData.map((_, idx) => (
                          <Cell
                            key={`pvp-${idx}`}
                            fill={THEME_COLORS[idx % THEME_COLORS.length]}
                            opacity={0.65}
                          />
                        ))}
                      </Pie>

                      {/* Anel Exterior: Sets */}
                      <Pie
                        data={areaData}
                        dataKey="sets"
                        nameKey="area"
                        cx="50%"
                        cy="50%"
                        innerRadius={78}
                        outerRadius={105}
                        paddingAngle={2}
                        cursor="pointer"
                        onClick={(entry) => handleAreaClick(entry.area)}
                        labelLine={false}
                        label={({ cx, cy, midAngle, innerRadius, outerRadius, percent, value }) => {
                          // Esconde em fatias demasiado finas (< 5%) para não sobrepor texto
                          if (percent < 0.05) return null;

                          const RADIAN = Math.PI / 180;
                          // Ponto médio exato da espessura do anel
                          const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
                          const x = cx + radius * Math.cos(-midAngle * RADIAN);
                          const y = cy + radius * Math.sin(-midAngle * RADIAN);

                          return (
                            <text
                              x={x}
                              y={y}
                              fill="#ffffff"
                              textAnchor="middle"
                              dominantBaseline="central"
                              fontSize={10}
                              fontWeight={600}
                            >
                              {num(value)}
                            </text>
                          );
                        }}
                      >
                        {areaData.map((_, idx) => (
                          <Cell
                            key={`sets-${idx}`}
                            fill={THEME_COLORS[idx % THEME_COLORS.length]}
                          />
                        ))}
                      </Pie>
                    </PieChart>
                  </ResponsiveContainer>
                </div>

                {/* Legenda Lateral Compacta em 2 Linhas */}
                <div className="w-full sm:w-[38%] flex flex-col justify-center max-h-full border-t sm:border-t-0 sm:border-l border-border/50 pt-2 sm:pt-0 sm:pl-3">
                  <div className="overflow-y-auto space-y-2 pr-1 max-h-[280px]">
                    {areaData.map((entry: any, index: number) => (
                      <button
                        key={entry.area}
                        type="button"
                        onClick={() => handleAreaClick(entry.area)}
                        className="w-full flex flex-col items-start p-1.5 rounded-md hover:bg-muted/60 transition-colors text-left group"
                      >
                        {/* Linha 1: [bola cor] Nome da Área */}
                        <div className="flex items-center gap-1.5 w-full min-w-0">
                          <span
                            className="h-2 w-2 rounded-full inline-block shrink-0"
                            style={{ backgroundColor: THEME_COLORS[index % THEME_COLORS.length] }}
                          />
                          <span className="text-xs font-semibold text-foreground truncate group-hover:text-primary transition-colors">
                            {entry.area}
                          </span>
                        </div>

                        {/* Linha 2: 62 sets · 3000€ (indentado para alinhar com o texto) */}
                        <div className="pl-3.5 flex items-center gap-1 font-mono text-[10px] text-muted-foreground">
                          <span>{num(entry.sets)} sets</span>
                          <span className="text-muted-foreground/40">·</span>
                          <span className="text-foreground/80 font-medium">{eur(entry.pvp)}</span>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <p className="py-12 text-center text-sm text-muted-foreground">
                Sem cópias arrumadas.
              </p>
            )}
          </CardContent>
        </Card>
        
        {/* Top temas: nº conjuntos vs peças*/}
        <Card>
          <CardHeader>
            <CardTitle>Top temas: nº de conjuntos vs. peças</CardTitle>
            <CardDescription>
              Quem lidera em número de caixas nem sempre lidera em volume de peças.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            <div>
              <p className="mb-2 text-xs font-medium text-muted-foreground">
                Por nº de conjuntos
              </p>
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

        {/* Temas vs PVP*/}
        <Card>
          <CardHeader>
            <CardTitle>Temas por PVP</CardTitle>
            <CardDescription>
              Ponderado pelo PVP total. Passe o rato para ver os subtemas; clique num tema para
              ver os conjuntos.
            </CardDescription>
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
                    content={renderTreemapNode as never}
                  >
                    <RechartsTooltip
                      content={({ active, payload }) => {
                        if (!active || !payload?.length) return null;
                        const entry = payload[0].payload as {
                          name: string;
                          size: number;
                          subthemes: { name: string; rrp: number }[];
                        };
                        return (
                          <div className="rounded-lg border border-border bg-popover p-2.5 shadow-md text-xs">
                            <div className="mb-1.5 flex items-center justify-between gap-4 border-b border-border pb-1.5 font-semibold">
                              <span>{entry.name}</span>
                              <span className="font-mono text-primary">{eur(entry.size)}</span>
                            </div>
                            <div className="space-y-1">
                              {entry.subthemes.map((sub) => (
                                <div
                                  key={sub.name}
                                  className="flex items-center justify-between gap-3"
                                >
                                  <span className="text-muted-foreground">{sub.name}</span>
                                  <span className="font-mono font-medium">{eur(sub.rrp)}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        );
                      }}
                    />
                  </Treemap>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="py-12 text-center text-sm text-muted-foreground">Sem dados.</p>
            )}
          </CardContent>
        </Card>

        {/* Anos de lançamento */}
        <Card>
          <CardHeader>
            <CardTitle>Anos de lançamento</CardTitle>
            <CardDescription>
              Volume total e distribuição por tema em cada ano.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {releaseYearData.length ? (
              <div className="flex flex-col gap-2">
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={releaseYearDataWithTotals}
                      margin={{ top: 24, right: 8, left: 0, bottom: 4 }}
                    >
                      <CartesianGrid
                        strokeDasharray="3 3"
                        vertical={false}
                        stroke="hsl(var(--border))"
                      />
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
                        content={({ active, payload, label }) => {
                          if (!active || !payload?.length) return null;
                          const total = payload.reduce(
                            (acc, curr) => acc + (Number(curr.value) || 0),
                            0
                          );

                          return (
                            <div className="rounded-lg border border-border bg-popover p-2.5 shadow-md text-xs">
                              <div className="flex items-center justify-between gap-4 font-semibold border-b border-border pb-1.5 mb-1.5">
                                <span>Ano {label}</span>
                                <span className="font-mono text-primary">{total} sets</span>
                              </div>
                              <div className="space-y-1">
                                {payload
                                  .filter((entry) => Number(entry.value) > 0)
                                  .map((entry) => (
                                    <div
                                      key={entry.name}
                                      className="flex items-center justify-between gap-3"
                                    >
                                      <div className="flex items-center gap-1.5">
                                        <span
                                          className="h-2 w-2 rounded-full inline-block shrink-0"
                                          style={{ backgroundColor: entry.color }}
                                        />
                                        <span className="text-muted-foreground">{entry.name}</span>
                                      </div>
                                      <span className="font-mono font-medium">
                                        {num(Number(entry.value))}
                                      </span>
                                    </div>
                                  ))}
                              </div>
                            </div>
                          );
                        }}
                      />

                      {releaseYearThemes.map((theme: string, index: number) => (
                        <Bar
                          key={theme}
                          dataKey={theme}
                          name={theme}
                          stackId="year"
                          fill={THEME_COLORS[index % THEME_COLORS.length]}
                          radius={
                            index === releaseYearThemes.length - 1
                              ? [3, 3, 0, 0]
                              : [0, 0, 0, 0]
                          }
                          cursor="pointer"
                          onClick={(entry) =>
                            onFilter({ tab: 'colecao', release_year: entry.year })
                          }
                        />
                      ))}

                      {/* Totais no topo de cada coluna */}
                      <Customized
                        component={({ formattedGraphicalItems }) => {
                          if (!formattedGraphicalItems?.length) return null;

                          const topsByIndex: Record<number, { x: number; width: number; minY: number }> = {};

                          formattedGraphicalItems.forEach((item: any) => {
                            item.props?.data?.forEach((bar: any, idx: number) => {
                              if (bar && typeof bar.y === 'number' && typeof bar.x === 'number') {
                                if (!topsByIndex[idx]) {
                                  topsByIndex[idx] = {
                                    x: bar.x,
                                    width: bar.width,
                                    minY: bar.y,
                                  };
                                } else {
                                  topsByIndex[idx].minY = Math.min(topsByIndex[idx].minY, bar.y);
                                }
                              }
                            });
                          });

                          return (
                            <g className="recharts-custom-totals">
                              {releaseYearDataWithTotals.map((item: any, idx: number) => {
                                const pos = topsByIndex[idx];
                                if (!pos || !item.total) return null;

                                return (
                                  <text
                                    key={`total-${item.year ?? idx}`}
                                    x={pos.x + pos.width / 2}
                                    y={pos.minY - 6}
                                    textAnchor="middle"
                                    fontSize={10}
                                    fontWeight={600}
                                    fill="hsl(var(--muted-foreground))"
                                  >
                                    {num(item.total)}
                                  </text>
                                );
                              })}
                            </g>
                          );
                        }}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                {/* Legenda em linha única com scroll horizontal e setas */}
                {releaseYearThemes.length > 1 && (
                  <div className="flex items-center gap-1.5 px-2 pt-1">
                    <button
                      type="button"
                      onClick={() => scrollThemes('left')}
                      className="shrink-0 p-1 text-muted-foreground hover:text-foreground transition-colors"
                      aria-label="Scroll left"
                    >
                      <ChevronLeft className="h-3.5 w-3.5" />
                    </button>

                    <div
                      ref={themesScrollRef}
                      className="flex items-center gap-3 overflow-x-auto scroll-smooth whitespace-nowrap text-[11px] py-1"
                      style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
                    >
                      {releaseYearThemes.map((theme: string, index: number) => (
                        <div
                          key={theme}
                          className="flex items-center gap-1.5 shrink-0 select-none text-muted-foreground"
                        >
                          <span
                            className="h-2 w-2 rounded-full inline-block shrink-0"
                            style={{ backgroundColor: THEME_COLORS[index % THEME_COLORS.length] }}
                          />
                          <span>{theme}</span>
                        </div>
                      ))}
                    </div>

                    <button
                      type="button"
                      onClick={() => scrollThemes('right')}
                      className="shrink-0 p-1 text-muted-foreground hover:text-foreground transition-colors"
                      aria-label="Scroll right"
                    >
                      <ChevronRight className="h-3.5 w-3.5" />
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <p className="py-12 text-center text-sm text-muted-foreground">
                Sem datas de lançamento.
              </p>
            )}
          </CardContent>
        </Card>
        
        {/* Custo Real vs PVP por canal*/}
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
                    <CartesianGrid
                      strokeDasharray="3 3"
                      vertical={false}
                      stroke="hsl(var(--border))"
                    />
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
                    <Bar
                      dataKey="custo"
                      name="Custo real"
                      fill="hsl(var(--muted-foreground))"
                      radius={[4, 4, 0, 0]}
                    />
                    <Bar dataKey="pvp" name="PVP" fill={THEME_COLORS[1]} radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="py-12 text-center text-sm text-muted-foreground">Sem dados.</p>
            )}
          </CardContent>
        </Card>

        {/* preço por peça */}
        <Card>
          <CardHeader>
            <CardTitle>Preço por peça</CardTitle>
            <CardDescription>
              Custo real vs. PVP por peça, cópia a cópia — quem valeu mesmo o desconto.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {pppCostData.length ? (
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
                      labelFormatter={(_, item) => {
                        const point = item?.[0]?.payload;
                        if (!point) return '';
                        return `${point.name}${point.setNumber ? ` · ${point.setNumber}` : ''}`;
                      }}
                    />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Scatter
                      data={pppRrpData}
                      name="PVP"
                      fill="hsl(var(--muted-foreground))"
                      opacity={0.5}
                    />
                    <Scatter
                      data={pppCostData}
                      name="Custo real"
                      fill="hsl(var(--warning))"
                      opacity={0.8}
                    />
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="py-12 text-center text-sm text-muted-foreground">Sem dados.</p>
            )}
          </CardContent>
        </Card>

        {/* Ano lançamento vs nº de peças */}
        <Card>
          <CardHeader>
            <CardTitle>Ano de lançamento vs. nº de peças</CardTitle>
            <CardDescription>
              Tendência logarítmica — sets grandes tornaram-se comuns, não a norma.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {yearPieceData.length ? (
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                    <XAxis
                      type="number"
                      dataKey="year"
                      name="Ano"
                      domain={['dataMin', 'dataMax']}
                      allowDecimals={false}
                      tick={{ fontSize: 11 }}
                      stroke="hsl(var(--muted-foreground))"
                    />
                    <YAxis
                      type="number"
                      dataKey="pieces"
                      name="Peças"
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
                        name === 'Ano' ? String(value) : num(value),
                        name,
                      ]}
                      labelFormatter={(_, item) => {
                        const point = item?.[0]?.payload;
                        if (!point?.name) return '';
                        return `${point.name}${point.setNumber ? ` · ${point.setNumber}` : ''}`;
                      }}
                    />
                    <Scatter
                      data={yearPieceData}
                      dataKey="pieces"
                      name="Conjuntos"
                      fill={THEME_COLORS[0]}
                      opacity={0.7}
                    />
                    {yearPieceTrend.length ? (
                      <Line
                        data={yearPieceTrend}
                        dataKey="pieces"
                        name="Tendência (log)"
                        stroke="hsl(var(--warning))"
                        strokeWidth={2}
                        dot={false}
                        activeDot={false}
                        legendType="none"
                        isAnimationActive={false}
                      />
                    ) : null}
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="py-12 text-center text-sm text-muted-foreground">
                Sem datas de lançamento.
              </p>
            )}
          </CardContent>
        </Card>

        {/* Distribuição por escalões de peças */}
        <Card>
          <CardHeader>
            <CardTitle>Distribuição por escalões de peças</CardTitle>
            <CardDescription>
              Porte volumétrico da coleção, do polybag ao titã de sala.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {totalBracketSets > 0 ? (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={pieceBracketData}
                    layout="vertical"
                    margin={{ top: 4, right: 56, left: 8, bottom: 4 }}
                  >
                    <CartesianGrid
                      strokeDasharray="3 3"
                      horizontal={false}
                      stroke="hsl(var(--border))"
                    />
                    <XAxis
                      type="number"
                      tick={{ fontSize: 11 }}
                      stroke="hsl(var(--muted-foreground))"
                      allowDecimals={false}
                    />
                    <YAxis
                      type="category"
                      dataKey="bracket"
                      tick={{ fontSize: 11 }}
                      stroke="hsl(var(--muted-foreground))"
                      width={136}
                    />
                    <RechartsTooltip
                      contentStyle={{
                        borderRadius: 10,
                        border: '1px solid hsl(var(--border))',
                        background: 'hsl(var(--popover))',
                        fontSize: 12,
                      }}
                      formatter={(value: number) => [
                        `${num(value)} conjuntos (${((value / totalBracketSets) * 100).toLocaleString('pt-PT', { maximumFractionDigits: 0 })} %)`,
                        'Conjuntos',
                      ]}
                    />
                    <Bar
                      dataKey="sets"
                      name="Conjuntos"
                      fill={THEME_COLORS[0]}
                      radius={[0, 4, 4, 0]}
                    >
                      <LabelList
                        dataKey="sets"
                        position="right"
                        formatter={(value: number) =>
                          `${value} (${((value / totalBracketSets) * 100).toLocaleString('pt-PT', { maximumFractionDigits: 0 })}%)`
                        }
                        style={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
                      />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="py-12 text-center text-sm text-muted-foreground">
                Sem dados de peças.
              </p>
            )}
          </CardContent>
        </Card>

      </div>     
    </div>
  );
}
