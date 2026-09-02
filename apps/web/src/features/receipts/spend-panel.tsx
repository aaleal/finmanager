import * as React from 'react';
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip as RechartsTooltip } from 'recharts';
import type { TooltipProps } from 'recharts';
import { PieChart as PieChartIcon } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { EmptyState, Skeleton } from '@/components/ui/feedback';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { eur, num } from '@/lib/format';
import type { FsFilter } from '@/lib/types';
import { FS_FILTER_OPTIONS } from './constants';
import { useCategorySpend } from './prices-api';

const SLICE_COLORS = [
  'hsl(var(--primary))',
  'hsl(var(--success))',
  'hsl(var(--warning))',
  'hsl(var(--destructive))',
  'hsl(var(--accent-foreground))',
  'hsl(var(--muted-foreground))',
];

const LEVEL_OPTIONS = [
  { value: '1', label: 'Nível 1' },
  { value: '2', label: 'Nível 2' },
  { value: '3', label: 'Nível 3' },
];

function SpendTooltip({ active, payload }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null;
  const entry = payload[0];
  return (
    <div className="rounded-lg border border-border bg-popover p-3 text-xs shadow-pop">
      <p className="font-medium">{typeof entry.name === 'string' ? entry.name : ''}</p>
      <p className="numeric">{eur(entry.value ?? null)}</p>
    </div>
  );
}

export function SpendPanel() {
  const [level, setLevel] = React.useState('1');
  const [fs, setFs] = React.useState<FsFilter>('all');

  const spend = useCategorySpend({ level: Number(level), fs });
  const rows = spend.data ?? [];

  const chartData = rows.map((row) => ({
    name: row.display_name_pt,
    value: Number(row.paid_eur),
  }));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Select value={level} onValueChange={setLevel}>
          <SelectTrigger className="w-32">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {LEVEL_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
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
      </div>

      <p className="text-xs text-muted-foreground">
        "Pago" é o que saiu da carteira; "nocional" é o que os artigos valiam — são iguais em todas
        as linhas que não são Fs.
      </p>

      {spend.isLoading ? (
        <Skeleton className="h-72 rounded-xl" />
      ) : rows.length === 0 ? (
        <EmptyState icon={PieChartIcon} title="Sem despesa registada para este nível." />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Despesa por categoria</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={320}>
                <PieChart>
                  <Pie
                    data={chartData}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={70}
                    outerRadius={110}
                    paddingAngle={2}
                  >
                    {chartData.map((entry, index) => (
                      <Cell key={entry.name} fill={SLICE_COLORS[index % SLICE_COLORS.length]} />
                    ))}
                  </Pie>
                  <RechartsTooltip content={<SpendTooltip />} />
                </PieChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Detalhe</CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Categoria</TableHead>
                    <TableHead>Pago</TableHead>
                    <TableHead>Nocional</TableHead>
                    <TableHead>Artigos</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((row) => (
                    <TableRow key={row.category_id ?? row.display_name_pt}>
                      <TableCell className="font-medium">{row.display_name_pt}</TableCell>
                      <TableCell className="numeric">{eur(row.paid_eur)}</TableCell>
                      <TableCell className="numeric">{eur(row.notional_eur)}</TableCell>
                      <TableCell className="numeric">{num(row.item_count)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
