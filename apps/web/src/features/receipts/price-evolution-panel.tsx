import * as React from 'react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { TooltipProps } from 'recharts';
import { AlertTriangle, Download, LineChart as LineChartIcon, Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { EmptyState, Skeleton } from '@/components/ui/feedback';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { EM_DASH, date, eur, num, percent } from '@/lib/format';
import type { FsFilter, ProductSearchResult } from '@/lib/types';
import { FS_FILTER_OPTIONS } from './constants';
import { ProductPicker } from './product-picker';
import { useExportPriceHistory, usePriceHistory } from './prices-api';

// One base colour per merchant, reused for both its lines (solid paid / dashed list).
const LINE_COLORS = [
  'hsl(var(--primary))',
  'hsl(var(--success))',
  'hsl(var(--warning))',
  'hsl(var(--destructive))',
];

interface ChartRow {
  observed_on: string;
  [seriesKey: string]: number | string | null;
}

function ChartTooltip({ active, payload, label }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null;
  return (
    <div className="space-y-1 rounded-lg border border-border bg-popover p-3 text-xs shadow-pop">
      <p className="font-medium">{date(String(label))}</p>
      {payload.map((entry) => (
        <p
          key={entry.dataKey}
          className="flex items-center justify-between gap-4"
          style={{ color: entry.color }}
        >
          <span>{entry.name}</span>
          <span className="numeric">{eur(entry.value ?? null)}</span>
        </p>
      ))}
    </div>
  );
}

export function PriceEvolutionPanel() {
  const [product, setProduct] = React.useState<ProductSearchResult | null>(null);
  const [fs, setFs] = React.useState<FsFilter>('all');

  const history = usePriceHistory(product?.id ?? null, fs);
  const exportHistory = useExportPriceHistory();

  const points = React.useMemo(() => history.data?.points ?? [], [history.data]);
  const shrinkflation = history.data?.shrinkflation ?? [];

  const hasWeights = points.some((point) => point.weight_kg !== null);
  const useWeightMetric = Boolean(history.data?.sold_by_weight) && hasWeights;

  const merchants = React.useMemo(() => {
    const seen = new Map<string, string>();
    for (const point of points) {
      if (!seen.has(point.merchant_id)) {
        seen.set(point.merchant_id, point.merchant_name ?? 'Comerciante');
      }
    }
    return Array.from(seen.entries()).map(([id, name]) => ({ id, name }));
  }, [points]);

  const rows = React.useMemo(() => {
    const byDate = new Map<string, ChartRow>();
    for (const point of points) {
      const row = byDate.get(point.observed_on) ?? { observed_on: point.observed_on };
      const listValue = useWeightMetric ? point.list_price_per_kg_eur : point.list_price_eur;
      const paidValue = useWeightMetric ? point.paid_price_per_kg_eur : point.paid_price_eur;
      row[`${point.merchant_id}__list`] = listValue !== null ? Number(listValue) : null;
      row[`${point.merchant_id}__paid`] = paidValue !== null ? Number(paidValue) : null;
      byDate.set(point.observed_on, row);
    }
    return Array.from(byDate.values()).sort((a, b) => a.observed_on.localeCompare(b.observed_on));
  }, [points, useWeightMetric]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="w-72">
          <ProductPicker
            value={product?.canonical_name ?? null}
            onSelect={setProduct}
            placeholder="Procurar produto…"
          />
        </div>
        <Select value={fs} onValueChange={(value) => setFs(value as FsFilter)}>
          <SelectTrigger className="w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {FS_FILTER_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button
          variant="outline"
          loading={exportHistory.isPending}
          disabled={!product}
          onClick={() => product && exportHistory.mutate({ productId: product.id, fs })}
        >
          <Download />
          Exportar CSV
        </Button>
      </div>

      {!product ? (
        <EmptyState icon={Search} title="Escolha um produto para ver a evolução do preço." />
      ) : history.isLoading ? (
        <Skeleton className="h-80 rounded-xl" />
      ) : points.length === 0 ? (
        <EmptyState
          icon={LineChartIcon}
          title="Ainda não há observações de preço para este produto."
        />
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle>{history.data?.canonical_name}</CardTitle>
              {!useWeightMetric ? (
                <p className="text-xs text-muted-foreground">
                  Sem pesos registados: o gráfico mostra o preço por embalagem.
                </p>
              ) : null}
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={360}>
                <LineChart data={rows} margin={{ left: 8, right: 16, top: 8, bottom: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis
                    dataKey="observed_on"
                    tickFormatter={(value: string) => date(value)}
                    tick={{ fontSize: 12 }}
                  />
                  <YAxis
                    tickFormatter={(value: number) => eur(value)}
                    width={90}
                    tick={{ fontSize: 12 }}
                  />
                  <RechartsTooltip content={<ChartTooltip />} />
                  {shrinkflation.map((signal, index) => (
                    <ReferenceLine
                      key={`${signal.merchant_id}-${signal.observed_on}-${index}`}
                      x={signal.observed_on}
                      stroke="hsl(var(--warning))"
                      strokeDasharray="4 4"
                    />
                  ))}
                  {merchants.map((merchant, index) => {
                    const color = LINE_COLORS[index % LINE_COLORS.length];
                    return (
                      <React.Fragment key={merchant.id}>
                        <Line
                          type="monotone"
                          dataKey={`${merchant.id}__paid`}
                          name={`${merchant.name} — pago`}
                          stroke={color}
                          strokeWidth={2}
                          dot={false}
                          connectNulls={false}
                        />
                        <Line
                          type="monotone"
                          dataKey={`${merchant.id}__list`}
                          name={`${merchant.name} — tabela`}
                          stroke={color}
                          strokeWidth={1.5}
                          strokeDasharray="5 4"
                          dot={false}
                          connectNulls={false}
                        />
                      </React.Fragment>
                    );
                  })}
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          {shrinkflation.length ? (
            <Card className="border-warning/30 bg-warning/5">
              <CardHeader className="flex-row items-center gap-2 space-y-0">
                <AlertTriangle className="size-4 text-warning" />
                <CardTitle className="text-warning">Encolhimento detetado</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 pt-0">
                <p className="text-xs text-muted-foreground">
                  A embalagem encolheu mais depressa do que o preço desceu.
                </p>
                <ul className="space-y-2">
                  {shrinkflation.map((signal, index) => (
                    <li
                      key={`${signal.merchant_id}-${signal.observed_on}-${index}`}
                      className="rounded-lg border border-border bg-card p-3 text-sm"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-medium">{signal.canonical_name}</span>
                        <span className="text-xs text-muted-foreground">
                          {signal.merchant_name ?? EM_DASH} · {date(signal.observed_on)}
                        </span>
                      </div>
                      <div className="mt-1 grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-muted-foreground sm:grid-cols-4">
                        <span>Observações: {num(signal.observations)}</span>
                        <span>
                          Peso: {num(Number(signal.current_weight_kg))} kg vs{' '}
                          {num(Number(signal.average_weight_kg))} kg (12 m)
                        </span>
                        <span>
                          Preço: {eur(signal.current_price_eur)} vs {eur(signal.average_price_eur)}
                        </span>
                        <span>Sinal de margem: {percent(Number(signal.margin_signal) * 100)}</span>
                      </div>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ) : null}
        </>
      )}
    </div>
  );
}
