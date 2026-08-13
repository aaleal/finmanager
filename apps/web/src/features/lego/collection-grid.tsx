import * as React from 'react';
import {
  ArrowDownWideNarrow,
  ArrowUpNarrowWide,
  Blocks,
  Filter,
  Package,
  Search,
  X,
} from 'lucide-react';
import type {
  CollectionSummary,
  LegoInstancePage,
  LegoSetInstance,
  StorageLocation,
} from '@/lib/types';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/primitives';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { EmptyState, Skeleton } from '@/components/ui/feedback';
import { eur, num, percent, signedEur } from '@/lib/format';
import { cn } from '@/lib/utils';
import {
  BUILD_STATE_LABELS,
  BUILD_STATE_VARIANT,
  COMPLETENESS_OPTIONS,
  CONDITION_LABELS,
  CONDITION_VARIANTS,
  OWNERSHIP_LABELS,
  RETIREMENT_OPTIONS,
  SORT_FIELDS,
} from './constants';
import type { InstanceFilters } from './api';

const ALL = '__all__';
/** Prefix that tells a whole-area choice apart from a single container. */
const AREA_PREFIX = 'area:';

function Thumb({ instance }: { instance: LegoSetInstance }) {
  const image = instance.photo_url ?? instance.set_model?.image_url ?? null;
  return (
    <div className="size-10 shrink-0 overflow-hidden rounded-md border border-border bg-muted">
      {image ? (
        <img src={image} alt="" className="size-full object-contain" loading="lazy" />
      ) : (
        <div className="flex size-full items-center justify-center text-muted-foreground">
          <Blocks className="size-4" />
        </div>
      )}
    </div>
  );
}

function RoiCell({ instance }: { instance: LegoSetInstance }) {
  const model = instance.set_model;

  // A gift has no cost basis, so cost-ROI is undefined by design. Rather than a
  // dead dash, fall back to the set's value against its original RRP — labelled,
  // so the two readings are never confused (M9.1).
  if (instance.roi_pct === null) {
    if (model?.rrp_roi_pct != null) {
      const up = Number(model.rrp_roi_pct) >= 0;
      return (
        <span
          className="numeric inline-flex items-center gap-1"
          title="Sem base de custo (prenda). Mostrado face ao PVP original."
        >
          <span className={cn('font-medium', up ? 'text-success' : 'text-destructive')}>
            {percent(model.rrp_roi_pct)}
          </span>
          <Badge variant="muted">PVP</Badge>
        </span>
      );
    }
    return (
      <span className="text-muted-foreground" title="Prenda ou conjunto sem valor definido">
        —
      </span>
    );
  }

  const positive = Number(instance.roi_pct) >= 0;
  return (
    <span className={cn('numeric font-medium', positive ? 'text-success' : 'text-destructive')}>
      {percent(instance.roi_pct)}
      <span className="ml-1 text-xs font-normal text-muted-foreground">
        {signedEur(instance.appreciation_eur)}
      </span>
    </span>
  );
}

/** Release year and, when the set has left the shelves, the year it retired. */
function YearsCell({ instance }: { instance: LegoSetInstance }) {
  const model = instance.set_model;
  if (!model?.release_year && !model?.retired_year) {
    return <span className="text-muted-foreground">—</span>;
  }
  return (
    <span className="numeric whitespace-nowrap">
      {model.release_year ?? '—'}
      {model.retired_year ? (
        <span className="text-muted-foreground"> › {model.retired_year}</span>
      ) : null}
    </span>
  );
}

function SetCell({ instance }: { instance: LegoSetInstance }) {
  const model = instance.set_model;
  return (
    <div className="flex items-center gap-3">
      <Thumb instance={instance} />
      <div className="min-w-0">
        <p className="flex items-center gap-1.5 truncate font-medium">
          <span className="truncate">{model?.name}</span>
          {!instance.is_complete ? (
            <Badge variant="destructive" title={instance.missing_parts ?? 'Incompleto'}>
              incompleto
            </Badge>
          ) : null}
          {model?.is_retired ? (
            <Badge variant="warning" title={`Retirado em ${model.retired_year}`}>
              retirado
            </Badge>
          ) : null}
        </p>
        <p className="numeric truncate text-xs text-muted-foreground">
          {model?.set_number ?? 'MOC'}
          {model?.piece_count ? ` · ${num(model.piece_count)} peças` : ''}
        </p>
      </div>
    </div>
  );
}

function GroupedRow({
  group,
  onSelect,
}: {
  group: { key: string; items: LegoSetInstance[] };
  onSelect: (instance: LegoSetInstance) => void;
}) {
  const first = group.items[0];
  const model = first.set_model;
  const totalCost = group.items.reduce((sum, item) => sum + Number(item.acquisition_cost_eur), 0);
  const totalValue = model?.current_value_eur
    ? Number(model.current_value_eur) * group.items.length
    : null;

  return (
    <TableRow
      className={cn('cursor-pointer', model?.is_retired && 'bg-warning/[0.06]')}
      onClick={() => onSelect(first)}
    >
      <TableCell>
        <SetCell instance={first} />
      </TableCell>
      <TableCell>
        <Badge variant="outline">{group.items.length} cópias</Badge>
      </TableCell>
      <TableCell>
        <YearsCell instance={first} />
      </TableCell>
      <TableCell className="numeric">{eur(totalCost)}</TableCell>
      <TableCell className="numeric">{eur(totalValue)}</TableCell>
      <TableCell>
        {totalValue !== null ? (
          <span
            className={cn(
              'numeric font-medium',
              totalValue - totalCost >= 0 ? 'text-success' : 'text-destructive',
            )}
          >
            {signedEur(totalValue - totalCost)}
          </span>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
      </TableCell>
    </TableRow>
  );
}

function SummaryStrip({ summary }: { summary: CollectionSummary }) {
  const items = [
    { label: 'cópias', value: num(summary.copies) },
    { label: 'conjuntos', value: num(summary.unique_sets) },
    { label: 'peças', value: num(summary.total_pieces) },
    { label: 'custo', value: eur(summary.total_cost_eur) },
    { label: 'valor atual', value: eur(summary.total_value_eur) },
  ];
  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-xl border border-border bg-card px-4 py-2.5 text-sm">
      {items.map((item) => (
        <span key={item.label} className="flex items-baseline gap-1.5">
          <span className="numeric font-semibold">{item.value}</span>
          <span className="text-xs text-muted-foreground">{item.label}</span>
        </span>
      ))}
      <span className="ml-auto text-xs text-muted-foreground">totais dos filtros aplicados</span>
    </div>
  );
}

export function CollectionGrid({
  data,
  isLoading,
  filters,
  setFilters,
  themes,
  storageLocations,
  grouped,
  onToggleGrouped,
  onSelect,
}: {
  data: LegoInstancePage | undefined;
  isLoading: boolean;
  filters: InstanceFilters & { [key: string]: string | undefined };
  setFilters: (patch: Record<string, string | undefined>) => void;
  themes: string[];
  storageLocations: StorageLocation[];
  grouped: boolean;
  onToggleGrouped: (value: boolean) => void;
  onSelect: (instance: LegoSetInstance) => void;
}) {
  const [showFilters, setShowFilters] = React.useState(false);
  const [searchDraft, setSearchDraft] = React.useState(filters.search ?? '');

  React.useEffect(() => setSearchDraft(filters.search ?? ''), [filters.search]);

  React.useEffect(() => {
    const timer = window.setTimeout(() => {
      if ((filters.search ?? '') !== searchDraft) setFilters({ search: searchDraft || undefined });
    }, 350);
    return () => window.clearTimeout(timer);
  }, [searchDraft, filters.search, setFilters]);

  const activeFilterCount = [
    filters.theme,
    filters.storage_location_id,
    filters.storage_area,
    filters.build_state,
    filters.condition,
    filters.completeness && filters.completeness !== 'all' ? filters.completeness : undefined,
    filters.retirement && filters.retirement !== 'all' ? filters.retirement : undefined,
    filters.ownership_status && filters.ownership_status !== 'IN_COLLECTION'
      ? filters.ownership_status
      : undefined,
  ].filter(Boolean).length;

  // Storage stays a flat table; only the picker is hierarchical, so "everything in
  // the garage" is one click without naming a container (M9.1).
  const areas = React.useMemo(() => {
    const map = new Map<string, StorageLocation[]>();
    for (const location of storageLocations) {
      const list = map.get(location.area) ?? [];
      list.push(location);
      map.set(location.area, list);
    }
    return [...map.entries()];
  }, [storageLocations]);

  const storageValue = filters.storage_location_id
    ? filters.storage_location_id
    : filters.storage_area
      ? `${AREA_PREFIX}${filters.storage_area}`
      : ALL;

  function setStorage(value: string) {
    if (value === ALL) setFilters({ storage_location_id: undefined, storage_area: undefined });
    else if (value.startsWith(AREA_PREFIX))
      setFilters({ storage_area: value.slice(AREA_PREFIX.length), storage_location_id: undefined });
    else setFilters({ storage_location_id: value, storage_area: undefined });
  }

  const groups = React.useMemo(() => {
    if (!grouped || !data) return [];
    const map = new Map<string, LegoSetInstance[]>();
    for (const item of data.items) {
      const list = map.get(item.lego_set_model_id) ?? [];
      list.push(item);
      map.set(item.lego_set_model_id, list);
    }
    return [...map.entries()].map(([key, items]) => ({ key, items }));
  }, [grouped, data]);

  const page = Number(filters.page ?? '1');
  const pageSize = Number(filters.page_size ?? '25');
  const totalPages = data ? Math.max(1, Math.ceil(data.total / pageSize)) : 1;
  const descending = (filters.direction ?? 'desc') === 'desc';

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-[14rem] flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-9"
            placeholder="Procurar por número, nome, tema ou notas…"
            value={searchDraft}
            onChange={(event) => setSearchDraft(event.target.value)}
          />
        </div>

        <Button
          variant={showFilters || activeFilterCount ? 'secondary' : 'outline'}
          onClick={() => setShowFilters((value) => !value)}
        >
          <Filter />
          Filtros
          {activeFilterCount ? (
            <Badge variant="default" className="ml-1">
              {activeFilterCount}
            </Badge>
          ) : null}
        </Button>

        <div className="flex items-center gap-1">
          <Select
            value={filters.sort ?? 'created'}
            onValueChange={(value) => setFilters({ sort: value })}
          >
            <SelectTrigger className="w-[9.5rem]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {SORT_FIELDS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            variant="outline"
            size="icon"
            aria-label={descending ? 'Ordenação descendente' : 'Ordenação ascendente'}
            title={descending ? 'Descendente' : 'Ascendente'}
            onClick={() => setFilters({ direction: descending ? 'asc' : 'desc' })}
          >
            {descending ? <ArrowDownWideNarrow /> : <ArrowUpNarrowWide />}
          </Button>
        </div>

        <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-sm shadow-soft">
          <Checkbox checked={grouped} onCheckedChange={(value) => onToggleGrouped(value === true)} />
          Agrupar por conjunto
        </label>
      </div>

      {showFilters ? (
        <div className="grid gap-3 rounded-xl border border-border bg-card p-4 sm:grid-cols-2 lg:grid-cols-4">
          <Select
            value={filters.theme ?? ALL}
            onValueChange={(value) => setFilters({ theme: value === ALL ? undefined : value })}
          >
            <SelectTrigger>
              <SelectValue placeholder="Tema" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>Todos os temas</SelectItem>
              {themes.map((theme) => (
                <SelectItem key={theme} value={theme}>
                  {theme}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={storageValue} onValueChange={setStorage}>
            <SelectTrigger>
              <SelectValue placeholder="Arrumação" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>Qualquer local</SelectItem>
              {areas.map(([area, items]) => (
                <SelectGroup key={area}>
                  <SelectLabel>{area}</SelectLabel>
                  <SelectItem value={`${AREA_PREFIX}${area}`}>Toda a área «{area}»</SelectItem>
                  {items.map((location) => (
                    <SelectItem key={location.id} value={location.id}>
                      {location.container ?? area}
                    </SelectItem>
                  ))}
                </SelectGroup>
              ))}
            </SelectContent>
          </Select>

          <Select
            value={filters.build_state ?? ALL}
            onValueChange={(value) => setFilters({ build_state: value === ALL ? undefined : value })}
          >
            <SelectTrigger>
              <SelectValue placeholder="Estado" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>Qualquer estado</SelectItem>
              {Object.entries(BUILD_STATE_LABELS).map(([value, label]) => (
                <SelectItem key={value} value={value}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select
            value={filters.condition ?? ALL}
            onValueChange={(value) => setFilters({ condition: value === ALL ? undefined : value })}
          >
            <SelectTrigger>
              <SelectValue placeholder="Condição" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>Qualquer condição</SelectItem>
              {Object.entries(CONDITION_LABELS).map(([value, label]) => (
                <SelectItem key={value} value={value}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select
            value={filters.ownership_status ?? 'IN_COLLECTION'}
            onValueChange={(value) => setFilters({ ownership_status: value })}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {Object.entries(OWNERSHIP_LABELS).map(([value, label]) => (
                <SelectItem key={value} value={value}>
                  {label}
                </SelectItem>
              ))}
              <SelectItem value={ALL}>Todos os estados</SelectItem>
            </SelectContent>
          </Select>

          <Select
            value={filters.completeness ?? 'all'}
            onValueChange={(value) => setFilters({ completeness: value })}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {COMPLETENESS_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select
            value={filters.retirement ?? 'all'}
            onValueChange={(value) => setFilters({ retirement: value })}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {RETIREMENT_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {activeFilterCount ? (
            <Button
              variant="ghost"
              size="sm"
              className="justify-start"
              onClick={() =>
                setFilters({
                  theme: undefined,
                  storage_location_id: undefined,
                  storage_area: undefined,
                  build_state: undefined,
                  condition: undefined,
                  completeness: undefined,
                  retirement: undefined,
                  ownership_status: undefined,
                })
              }
            >
              <X />
              Limpar filtros
            </Button>
          ) : null}
        </div>
      ) : null}

      {data ? <SummaryStrip summary={data.summary} /> : null}

      <div className="overflow-hidden rounded-xl border border-border bg-card shadow-soft">
        {isLoading ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 6 }).map((_, index) => (
              <Skeleton key={index} className="h-12" />
            ))}
          </div>
        ) : !data || data.items.length === 0 ? (
          <EmptyState
            className="border-0"
            icon={Package}
            title="Nada por aqui"
            description="Não há cópias que correspondam aos filtros aplicados."
          />
        ) : grouped ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Conjunto</TableHead>
                <TableHead>Cópias</TableHead>
                <TableHead>Ano</TableHead>
                <TableHead>Custo</TableHead>
                <TableHead>Valor</TableHead>
                <TableHead>Ganho</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {groups.map((group) => (
                <GroupedRow key={group.key} group={group} onSelect={onSelect} />
              ))}
            </TableBody>
          </Table>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Conjunto</TableHead>
                <TableHead>Tema</TableHead>
                <TableHead>Ano</TableHead>
                <TableHead>Arrumação</TableHead>
                <TableHead>Estado</TableHead>
                <TableHead>Condição</TableHead>
                <TableHead className="text-right">Custo</TableHead>
                <TableHead className="text-right">PVP</TableHead>
                <TableHead className="text-right">Valor</TableHead>
                <TableHead className="text-right">ROI</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.items.map((instance) => (
                <TableRow
                  key={instance.id}
                  className={cn(
                    'cursor-pointer',
                    // Retirement is a durable property of the row, so it tints the
                    // whole line as well as carrying a labelled badge.
                    instance.set_model?.is_retired && 'bg-warning/[0.06]',
                  )}
                  onClick={() => onSelect(instance)}
                >
                  <TableCell>
                    <SetCell instance={instance} />
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {instance.set_model?.theme ?? '—'}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    <YearsCell instance={instance} />
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {instance.storage_label ?? '—'}
                  </TableCell>
                  <TableCell>
                    {instance.build_state ? (
                      <Badge variant={BUILD_STATE_VARIANT}>
                        {BUILD_STATE_LABELS[instance.build_state]}
                      </Badge>
                    ) : (
                      '—'
                    )}
                  </TableCell>
                  <TableCell>
                    {instance.condition ? (
                      <Badge variant={CONDITION_VARIANTS[instance.condition]}>
                        {CONDITION_LABELS[instance.condition]}
                      </Badge>
                    ) : (
                      '—'
                    )}
                  </TableCell>
                  <TableCell className="numeric text-right">
                    {eur(instance.acquisition_cost_eur)}
                  </TableCell>
                  <TableCell className="numeric text-right text-muted-foreground">
                    {eur(instance.set_model?.rrp_eur)}
                  </TableCell>
                  <TableCell className="numeric text-right">
                    <span className={instance.set_model?.value_is_stale ? 'text-warning' : ''}>
                      {eur(instance.current_value_eur)}
                    </span>
                  </TableCell>
                  <TableCell className="text-right">
                    <RoiCell instance={instance} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>

      {data && data.total > pageSize ? (
        <div className="flex items-center justify-between gap-4 text-sm">
          <p className="text-muted-foreground">
            {data.total} cópia(s) · página {page} de {totalPages}
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => setFilters({ page: String(page - 1) })}
            >
              Anterior
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => setFilters({ page: String(page + 1) })}
            >
              Seguinte
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
