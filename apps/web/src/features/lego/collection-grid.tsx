import * as React from 'react';
import {
  ArrowDown,
  ArrowDownWideNarrow,
  ArrowUp,
  ArrowUpNarrowWide,
  Blocks,
  ChevronsLeft,
  ChevronsRight,
  ChevronsUpDown,
  Filter,
  Gift,
  Package,
  Search,
  X,
} from 'lucide-react';
import type {
  BuildState,
  CollectionSummary,
  Condition,
  LegoInstancePage,
  LegoSetInstance,
  StorageLocation,
} from '@/lib/types';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Checkbox, TooltipContent, TooltipRoot, TooltipTrigger } from '@/components/ui/primitives';
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
import { EmptyState, Skeleton } from '@/components/ui/feedback';
import { eur, num, percent, signedEur } from '@/lib/format';
import { cn } from '@/lib/utils';
import {
  BUILD_STATE_LABELS,
  BUILD_STATE_VARIANT,
  COMPLETENESS_OPTIONS,
  CONDITION_LABELS,
  CONDITION_VARIANTS,
  COPIES_OPTIONS,
  DENSITY_OPTIONS,
  FS_OPTIONS,
  GIFT_OPTIONS,
  OWNERSHIP_LABELS,
  PAGE_SIZES,
  RETIREMENT_OPTIONS,
  SORT_FIELDS,
  SOURCE_LABELS,
} from './constants';
import { StorageFilter } from './storage-filter';
import type { InstanceFilters } from './api';

const ALL = '__all__';

type RoiBasis = 'cost' | 'rrp';

/** `roi_basis` is absent for the default (cost) reading, so the URL stays clean. */
function roiBasis(filters: Record<string, string | undefined>): RoiBasis {
  return filters.roi_basis === 'rrp' ? 'rrp' : 'cost';
}

type Density = 'compact' | 'cozy' | 'large';

/** `density` is absent for the default (compact) reading, mirroring `roiBasis`. */
function resolveDensity(filters: Record<string, string | undefined>): Density {
  return filters.density === 'cozy' || filters.density === 'large' ? filters.density : 'compact';
}

const THUMB_SIZE_CLASS: Record<Density, string> = {
  compact: 'size-10',
  cozy: 'size-16',
  large: 'size-24',
};

const ROI_BASIS_OPTIONS: { value: RoiBasis; label: string; hint: string }[] = [
  { value: 'cost', label: 'Pago', hint: 'ROI calculado sobre o valor efectivamente pago.' },
  { value: 'rrp', label: 'PVP', hint: 'ROI calculado sobre o PVP original do conjunto.' },
];

/** A debounced text draft for a single numeric filter key, mirroring the search box. */
function useFilterDraft(value: string | undefined, onCommit: (value: string | undefined) => void) {
  const [draft, setDraft] = React.useState(value ?? '');
  React.useEffect(() => setDraft(value ?? ''), [value]);
  React.useEffect(() => {
    const timer = window.setTimeout(() => {
      if ((value ?? '') !== draft) onCommit(draft || undefined);
    }, 350);
    return () => window.clearTimeout(timer);
  }, [draft, value, onCommit]);
  return [draft, setDraft] as const;
}

/** One "mín/máx" numeric range, styled to sit next to the Select filters at the same height. */
function RangeFilter({
  label,
  unit,
  min,
  max,
  onMinChange,
  onMaxChange,
}: {
  label: string;
  unit: string;
  min: string | undefined;
  max: string | undefined;
  onMinChange: (value: string | undefined) => void;
  onMaxChange: (value: string | undefined) => void;
}) {
  const [minDraft, setMinDraft] = useFilterDraft(min, onMinChange);
  const [maxDraft, setMaxDraft] = useFilterDraft(max, onMaxChange);
  return (
    <div className="flex h-9 items-center gap-1.5 rounded-lg border border-input bg-card px-2.5 text-sm shadow-soft">
      <span className="shrink-0 text-xs text-muted-foreground">
        {label} ({unit})
      </span>
      <input
        type="number"
        inputMode="decimal"
        placeholder="Mín"
        value={minDraft}
        onChange={(event) => setMinDraft(event.target.value)}
        className="w-0 min-w-0 flex-1 bg-transparent text-right outline-none placeholder:text-placeholder"
      />
      <span className="text-muted-foreground">–</span>
      <input
        type="number"
        inputMode="decimal"
        placeholder="Máx"
        value={maxDraft}
        onChange={(event) => setMaxDraft(event.target.value)}
        className="w-0 min-w-0 flex-1 bg-transparent text-right outline-none placeholder:text-placeholder"
      />
    </div>
  );
}

function Thumb({ instance, density = 'compact' }: { instance: LegoSetInstance; density?: Density }) {
  const image =
    instance.photo_url ?? instance.display_image_url ?? instance.set_model?.image_url ?? null;
  const box = (
    <div
      className={cn(
        THUMB_SIZE_CLASS[density],
        'shrink-0 overflow-hidden rounded-md border border-border bg-muted',
      )}
    >
      {image ? (
        <img src={image} alt="" className="size-full object-contain" loading="lazy" />
      ) : (
        <div className="flex size-full items-center justify-center text-muted-foreground">
          <Blocks className="size-4" />
        </div>
      )}
    </div>
  );
  if (!image) return box;
  // Portalled tooltip content escapes the table's overflow-hidden ancestor.
  return (
    <TooltipRoot>
      <TooltipTrigger asChild>{box}</TooltipTrigger>
      <TooltipContent
        side="right"
        className="max-w-none border border-border bg-card p-1 shadow-pop"
      >
        <img src={image} alt="" className="max-h-72 max-w-72 rounded object-contain" />
      </TooltipContent>
    </TooltipRoot>
  );
}

/** Shared percentage + amount presentation for any ROI reading — used by the
 * per-copy ROI column and the grouped-view rollup, so both render identically. */
function RoiValue({
  pct,
  amountEur,
  sublabel,
  hint,
}: {
  pct: number;
  amountEur?: number;
  sublabel?: string;
  hint?: string;
}) {
  const positive = pct >= 0;
  return (
    <span className="block" title={hint}>
      <span
        className={cn('numeric block font-medium', positive ? 'text-success' : 'text-destructive')}
      >
        {percent(pct)}
      </span>
      {sublabel ? (
        <span className="block text-xs text-muted-foreground">{sublabel}</span>
      ) : (
        <span className="numeric block text-xs text-muted-foreground">
          {signedEur(amountEur ?? 0)}
        </span>
      )}
    </span>
  );
}

/** `basis=rrp` is an alternate, explicit reading — today's value against the
 * original PVP for every row — never a silent replacement of the cost ROI
 * headline (ADR-0010). `basis=cost` keeps the M9.1 PVP fallback for gifts. */
function RoiCell({ instance, basis }: { instance: LegoSetInstance; basis: RoiBasis }) {
  const model = instance.set_model;

  if (basis === 'rrp') {
    if (model?.rrp_roi_pct == null) {
      return (
        <span className="text-muted-foreground" title="Conjunto sem PVP definido">
          —
        </span>
      );
    }
    return (
      <RoiValue
        pct={Number(model.rrp_roi_pct)}
        amountEur={Number(model.rrp_appreciation_eur)}
        hint={
          instance.roi_pct != null
            ? `Face ao pago: ${percent(instance.roi_pct)} (${signedEur(instance.appreciation_eur)})`
            : undefined
        }
      />
    );
  }

  // A gift has no cost basis, so cost-ROI is undefined by design. Rather than a
  // dead dash, fall back to the set's value against its original RRP — labelled,
  // so the two readings are never confused (M9.1).
  if (instance.roi_pct === null) {
    if (model?.rrp_roi_pct != null) {
      return (
        <RoiValue
          pct={Number(model.rrp_roi_pct)}
          sublabel="face ao PVP"
          hint="Sem base de custo (prenda). Mostrado face ao PVP original."
        />
      );
    }
    return (
      <span className="text-muted-foreground" title="Prenda ou conjunto sem valor definido">
        —
      </span>
    );
  }

  return (
    <RoiValue
      pct={Number(instance.roi_pct)}
      amountEur={Number(instance.appreciation_eur)}
      hint={
        model?.rrp_roi_pct != null
          ? `Face ao PVP: ${percent(model.rrp_roi_pct)} (${signedEur(model.rrp_appreciation_eur)})`
          : undefined
      }
    />
  );
}

/** PVP is the headline — it's what the set is "worth" on the shelf — with the
 * actual amount paid underneath, smaller, since it's often a discount or a gift. */
function CostCell({ rrpEur, paidEur }: { rrpEur: number | null; paidEur: number }) {
  // Discount vs. PVP, e.g. "149,99 € (60%)" — negative when paid above list price.
  let diffPct = 0;
  if (rrpEur !== 0 && rrpEur !== null) {
    diffPct = Math.round(((rrpEur - paidEur) / rrpEur) * 100);
  }
  return (
    <span className="block">
      <span className="numeric block font-medium">{eur(rrpEur)}</span>
      <span className="numeric block text-xs text-muted-foreground">
        {eur(paidEur)}
        {diffPct !== 0 ? (
          <span
            className="text-[10px]"
            title={diffPct > 0 ? `${diffPct}% abaixo do PVP` : `${-diffPct}% acima do PVP`}
          >
            {' '}
            ({diffPct}%)
          </span>
        ) : null}
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

/**
 * The name is the only free-text column, so it is the one that gets capped: it
 * truncates with the full name on hover, which keeps the ten columns inside the
 * viewport instead of pushing them behind a horizontal scrollbar.
 */
function SetCell({ instance, density = 'compact' }: { instance: LegoSetInstance; density?: Density }) {
  const model = instance.set_model;
  return (
    <div className="flex max-w-[15rem] items-center gap-2.5">
      <Thumb instance={instance} density={density} />
      <div className="min-w-0">
        <p className="flex items-center gap-1.5 font-medium">
          <span className="truncate" title={model?.name}>
            {model?.name}
          </span>
          {!instance.is_complete ? (
            <Badge
              variant="destructive"
              className="shrink-0"
              title={instance.missing_parts ?? 'Incompleto'}
            >
              incompleto
            </Badge>
          ) : null}
          {model?.is_retired ? (
            <Badge
              variant="warning"
              className="shrink-0"
              title={`Retirado em ${model.retired_year}`}
            >
              retirado
            </Badge>
          ) : null}
          {instance.is_potential_gift ? (
            <Badge variant="outline" className="shrink-0 gap-1" title="Potencial presente">
              <Gift className="size-3" />
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

/** A column header that sorts: click to sort, click again to flip the direction. */
function SortHead({
  field,
  label,
  filters,
  setFilters,
  align = 'left',
  className,
}: {
  field: string;
  label: string;
  filters: Record<string, string | undefined>;
  setFilters: (patch: Record<string, string | undefined>) => void;
  align?: 'left' | 'right';
  className?: string;
}) {
  const active = (filters.sort ?? 'created') === field;
  const descending = (filters.direction ?? 'desc') === 'desc';

  return (
    <TableHead
      aria-sort={active ? (descending ? 'descending' : 'ascending') : 'none'}
      className={cn(align === 'right' && 'text-right', className)}
    >
      <button
        type="button"
        onClick={() =>
          setFilters({
            sort: field,
            // A fresh column starts descending for numbers and ascending for text.
            direction: active
              ? descending
                ? 'asc'
                : 'desc'
              : TEXT_FIELDS.has(field)
                ? 'asc'
                : 'desc',
            page: '1',
          })
        }
        className={cn(
          'group inline-flex items-center gap-1 uppercase transition-colors hover:text-foreground',
          align === 'right' && 'flex-row-reverse',
          active ? 'text-foreground' : 'text-muted-foreground',
        )}
      >
        {label}
        {active ? (
          descending ? (
            <ArrowDown className="size-3" />
          ) : (
            <ArrowUp className="size-3" />
          )
        ) : (
          <ChevronsUpDown className="size-3 opacity-0 transition-opacity group-hover:opacity-60" />
        )}
      </button>
    </TableHead>
  );
}

/** The ROI column ranks by what was paid or by the original PVP (ADR-0010's
 * second reading); the reading itself is picked by `RoiBasisSwitch` in the
 * toolbar, not here — this header only ever reports which one is active. */
function RoiHead({
  filters,
  setFilters,
}: {
  filters: Record<string, string | undefined>;
  setFilters: (patch: Record<string, string | undefined>) => void;
}) {
  return (
    <SortHead
      field="roi"
      label={roiBasis(filters) === 'rrp' ? 'ROI (PVP)' : 'ROI (pago)'}
      filters={filters}
      setFilters={setFilters}
      align="right"
    />
  );
}

/** Lives in the toolbar, not the table header: it changes what every ROI cell
 * means and what `sort=roi` ranks by, so it is a view-wide mode rather than
 * column decoration. */
function RoiBasisSwitch({
  filters,
  setFilters,
}: {
  filters: Record<string, string | undefined>;
  setFilters: (patch: Record<string, string | undefined>) => void;
}) {
  const basis = roiBasis(filters);

  function select(value: RoiBasis) {
    setFilters({ roi_basis: value === 'cost' ? undefined : value, page: '1' });
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLButtonElement>, index: number) {
    if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return;
    event.preventDefault();
    select(ROI_BASIS_OPTIONS[(index + 1) % ROI_BASIS_OPTIONS.length].value);
  }

  return (
    <div
      role="radiogroup"
      aria-label="Base de cálculo do ROI"
      className="flex h-9 items-center gap-1 rounded-lg border border-input bg-card px-2 shadow-soft"
    >
      <span className="shrink-0 text-xs text-muted-foreground">ROI face a</span>
      {ROI_BASIS_OPTIONS.map((option, index) => {
        const selected = option.value === basis;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={selected}
            tabIndex={selected ? 0 : -1}
            title={option.hint}
            onClick={() => select(option.value)}
            onKeyDown={(event) => handleKeyDown(event, index)}
            className={cn(
              'h-6 rounded-md px-2 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              selected
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

const TEXT_FIELDS = new Set(['number', 'name', 'theme', 'storage', 'ownership']);

/** Every distinct build state / condition present across the group's copies,
 * each tagged with a count when more than one copy shares it — the grouped-view
 * equivalent of the flat table's per-copy Estado column. */
function StateSummaryCell({ items }: { items: LegoSetInstance[] }) {
  const buildCounts = new Map<BuildState, number>();
  const conditionCounts = new Map<Condition, number>();
  for (const item of items) {
    if (item.build_state) {
      buildCounts.set(item.build_state, (buildCounts.get(item.build_state) ?? 0) + 1);
    }
    if (item.condition) {
      conditionCounts.set(item.condition, (conditionCounts.get(item.condition) ?? 0) + 1);
    }
  }
  if (buildCounts.size === 0 && conditionCounts.size === 0) {
    return <span className="text-muted-foreground">—</span>;
  }
  return (
    <div className="flex flex-col items-start gap-1">
      {[...buildCounts.entries()].map(([state, count]) => (
        <Badge key={state} variant={BUILD_STATE_VARIANT}>
          {BUILD_STATE_LABELS[state]}
          {count > 1 ? ` \u00d7${count}` : ''}
        </Badge>
      ))}
      {[...conditionCounts.entries()].map(([condition, count]) => (
        <Badge key={condition} variant={CONDITION_VARIANTS[condition]}>
          {CONDITION_LABELS[condition]}
          {count > 1 ? ` \u00d7${count}` : ''}
        </Badge>
      ))}
    </div>
  );
}

/** The grouped-view rollup of `RoiCell`: same basis toggle, same percentage +
 * amount presentation (via `RoiValue`), just summed/scaled across every copy
 * in the group instead of read off a single instance. */
function GroupRoiCell({ items, basis }: { items: LegoSetInstance[]; basis: RoiBasis }) {
  const model = items[0].set_model;
  const totalCost = items.reduce((sum, item) => sum + Number(item.acquisition_cost_eur), 0);
  const totalValue = model?.current_value_eur
    ? Number(model.current_value_eur) * items.length
    : null;

  if (basis === 'rrp') {
    if (model?.rrp_roi_pct == null) {
      return (
        <span className="text-muted-foreground" title="Conjunto sem PVP definido">
          —
        </span>
      );
    }
    return (
      <RoiValue
        pct={Number(model.rrp_roi_pct)}
        amountEur={Number(model.rrp_appreciation_eur ?? 0) * items.length}
      />
    );
  }

  // Same M9.1 gift fallback as the per-copy cell: no cost basis (every copy in
  // the group was a gift) falls back to the PVP reading, clearly labelled.
  if (totalCost === 0) {
    if (model?.rrp_roi_pct != null) {
      return (
        <RoiValue
          pct={Number(model.rrp_roi_pct)}
          sublabel="face ao PVP"
          hint="Sem base de custo (prendas/ofertas). Mostrado face ao PVP original."
        />
      );
    }
    return (
      <span className="text-muted-foreground" title="Prendas ou conjunto sem valor definido">
        —
      </span>
    );
  }

  if (totalValue === null) {
    return <span className="text-muted-foreground">—</span>;
  }

  return (
    <RoiValue
      pct={((totalValue - totalCost) / totalCost) * 100}
      amountEur={totalValue - totalCost}
    />
  );
}

function GroupedRow({
  group,
  basis,
  density,
  onSelect,
}: {
  group: { key: string; items: LegoSetInstance[] };
  basis: RoiBasis;
  density: Density;
  onSelect: (instance: LegoSetInstance) => void;
}) {
  const first = group.items[0];
  const model = first.set_model;
  const totalCost = group.items.reduce((sum, item) => sum + Number(item.acquisition_cost_eur), 0);
  const totalRrp = model?.rrp_eur ? Number(model.rrp_eur) * group.items.length : null;
  const totalValue = model?.current_value_eur
    ? Number(model.current_value_eur) * group.items.length
    : null;

  return (
    <TableRow
      className={cn('cursor-pointer', model?.is_retired && 'bg-warning/[0.06]')}
      onClick={() => onSelect(first)}
    >
      <TableCell>
        <SetCell instance={first} density={density} />
      </TableCell>
      <TableCell className="text-muted-foreground">{model?.theme ?? '—'}</TableCell>
      <TableCell>
        <Badge variant="outline">{group.items.length} cópias</Badge>
      </TableCell>
      <TableCell className="text-muted-foreground">
        <YearsCell instance={first} />
      </TableCell>
      <TableCell>
        <StateSummaryCell items={group.items} />
      </TableCell>
      <TableCell className="numeric">
        <CostCell rrpEur={totalRrp} paidEur={totalCost} />
      </TableCell>
      <TableCell className="numeric">{eur(totalValue)}</TableCell>
      <TableCell className="text-right">
        <GroupRoiCell items={group.items} basis={basis} />
      </TableCell>
    </TableRow>
  );
}

function SummaryStrip({ summary, basis }: { summary: CollectionSummary; basis: RoiBasis }) {
  const items = [
    { label: 'cópias', value: num(summary.copies) },
    { label: 'conjuntos', value: num(summary.unique_sets) },
    { label: 'peças', value: num(summary.total_pieces) },
    { label: 'custo', value: eur(summary.total_cost_eur) },
    { label: 'pvp', value: eur(summary.total_rrp_eur) },
    { label: 'valor atual', value: eur(summary.total_value_eur) },
    { label: 'temas', value: num(summary.unique_themes) },
  ];
  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-xl border border-border bg-card px-4 py-2.5 text-sm">
      {items.map((item) => (
        <span key={item.label} className="flex items-baseline gap-1.5">
          <span className="numeric font-semibold">{item.value}</span>
          <span className="text-xs text-muted-foreground">{item.label}</span>
        </span>
      ))}
      <span className="text-xs text-muted-foreground">
        ROI face a {basis === 'rrp' ? 'PVP' : 'valor pago'}
      </span>
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
    filters.acquisition_source,
    filters.release_year,
    filters.completeness && filters.completeness !== 'all' ? filters.completeness : undefined,
    filters.retirement && filters.retirement !== 'all' ? filters.retirement : undefined,
    filters.copies && filters.copies !== 'all' ? filters.copies : undefined,
    filters.fs && filters.fs !== 'all' ? filters.fs : undefined,
    filters.gift && filters.gift !== 'all' ? filters.gift : undefined,
    filters.paid_min,
    filters.paid_max,
    filters.rrp_min,
    filters.rrp_max,
    filters.roi_min,
    filters.roi_max,
    filters.ownership_status && filters.ownership_status !== 'IN_COLLECTION'
      ? filters.ownership_status
      : undefined,
  ].filter(Boolean).length;

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
  const density = resolveDensity(filters);

  const clearFilters = () =>
    setFilters({
      theme: undefined,
      storage_location_id: undefined,
      storage_area: undefined,
      build_state: undefined,
      condition: undefined,
      acquisition_source: undefined,
      release_year: undefined,
      completeness: undefined,
      retirement: undefined,
      copies: undefined,
      fs: undefined,
      gift: undefined,
      paid_min: undefined,
      paid_max: undefined,
      rrp_min: undefined,
      rrp_max: undefined,
      roi_min: undefined,
      roi_max: undefined,
      ownership_status: undefined,
      page: '1',
    });

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

        {!showFilters && activeFilterCount ? (
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label="Limpar filtros"
            title="Limpar filtros"
            onClick={clearFilters}
          >
            <X />
          </Button>
        ) : null}

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

        <RoiBasisSwitch filters={filters} setFilters={setFilters} />

        <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-sm shadow-soft">
          <Checkbox
            checked={grouped}
            onCheckedChange={(value) => onToggleGrouped(value === true)}
          />
          Agrupar por conjunto
        </label>

        <div className="flex items-center gap-1.5">
          <span className="text-xs text-muted-foreground">Densidade</span>
          <Select
            value={density}
            onValueChange={(value) => setFilters({ density: value === 'compact' ? undefined : value })}
          >
            <SelectTrigger className="w-[8.5rem]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {DENSITY_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {filters.release_year ? (
          <Badge variant="secondary" className="gap-1.5 py-1.5 pl-2.5 pr-1.5 text-sm">
            Ano: {filters.release_year}
            <button
              type="button"
              aria-label="Remover filtro de ano"
              className="rounded-full p-0.5 hover:bg-muted"
              onClick={() => setFilters({ release_year: undefined, page: '1' })}
            >
              <X className="size-3" />
            </button>
          </Badge>
        ) : null}
      </div>

      {showFilters ? (
        <div className="grid gap-3 rounded-xl border border-border bg-card p-4 sm:grid-cols-4 lg:grid-cols-8">
          <div className="sm:col-span-2 lg:col-span-2">
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
          </div>

          <div className="sm:col-span-2 lg:col-span-2">
            <StorageFilter
              locations={storageLocations}
              value={{
                storage_location_id: filters.storage_location_id,
                storage_area: filters.storage_area,
              }}
              onChange={(selection) =>
                setFilters({
                  storage_location_id: selection.storage_location_id,
                  storage_area: selection.storage_area,
                })
              }
            />
          </div>

          <div className="sm:col-span-2 lg:col-span-2">
            <Select
              value={filters.build_state ?? ALL}
              onValueChange={(value) =>
                setFilters({ build_state: value === ALL ? undefined : value })
              }
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
          </div>

          <div className="sm:col-span-2 lg:col-span-2">
            <Select
              value={filters.condition ?? ALL}
              onValueChange={(value) =>
                setFilters({ condition: value === ALL ? undefined : value })
              }
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
          </div>

          <div className="sm:col-span-2 lg:col-span-2">
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
          </div>

          <div className="sm:col-span-2 lg:col-span-2">
            <Select
              value={filters.retirement ?? 'all'}
              onValueChange={(value) => setFilters({ retirement: value, page: '1' })}
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
          </div>

          <div className="sm:col-span-2 lg:col-span-2">
            <Select
              value={filters.copies ?? 'all'}
              onValueChange={(value) => setFilters({ copies: value, page: '1' })}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {COPIES_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="sm:col-span-2 lg:col-span-2">
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
          </div>

          <div className="sm:col-span-2 lg:col-span-2">
            <Select
              value={filters.fs ?? 'all'}
              onValueChange={(value) => setFilters({ fs: value, page: '1' })}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {FS_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="sm:col-span-2 lg:col-span-2">
            <Select
              value={filters.gift ?? 'all'}
              onValueChange={(value) => setFilters({ gift: value, page: '1' })}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {GIFT_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="sm:col-span-2 lg:col-span-2">
            <Select
              value={filters.acquisition_source ?? ALL}
              onValueChange={(value) =>
                setFilters({ acquisition_source: value === ALL ? undefined : value })
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="Origem" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>Qualquer origem</SelectItem>
                {Object.entries(SOURCE_LABELS).map(([value, label]) => (
                  <SelectItem key={value} value={value}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="sm:col-span-2 lg:col-span-2">
            <RangeFilter
              label="Pago"
              unit="€"
              min={filters.paid_min}
              max={filters.paid_max}
              onMinChange={(value) => setFilters({ paid_min: value, page: '1' })}
              onMaxChange={(value) => setFilters({ paid_max: value, page: '1' })}
            />
          </div>

          <div className="sm:col-span-2 lg:col-span-2">
            <RangeFilter
              label="PVP"
              unit="€"
              min={filters.rrp_min}
              max={filters.rrp_max}
              onMinChange={(value) => setFilters({ rrp_min: value, page: '1' })}
              onMaxChange={(value) => setFilters({ rrp_max: value, page: '1' })}
            />
          </div>

          <div className="sm:col-span-2 lg:col-span-2">
            <RangeFilter
              label="ROI"
              unit="%"
              min={filters.roi_min}
              max={filters.roi_max}
              onMinChange={(value) => setFilters({ roi_min: value, page: '1' })}
              onMaxChange={(value) => setFilters({ roi_max: value, page: '1' })}
            />
          </div>

          {activeFilterCount ? (
            <Button variant="ghost" size="sm" className="justify-start" onClick={clearFilters}>
              <X />
              Limpar filtros
            </Button>
          ) : null}
        </div>
      ) : null}

      {data ? <SummaryStrip summary={data.summary} basis={roiBasis(filters)} /> : null}

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
                <SortHead field="name" label="Conjunto" filters={filters} setFilters={setFilters} />
                <SortHead field="theme" label="Tema" filters={filters} setFilters={setFilters} />
                <SortHead field="copies" label="Cópias" filters={filters} setFilters={setFilters} />
                <SortHead field="year" label="Ano" filters={filters} setFilters={setFilters} />
                <SortHead field="state" label="Estado" filters={filters} setFilters={setFilters} />
                <SortHead
                  field="cost"
                  label="PVP / Pago"
                  filters={filters}
                  setFilters={setFilters}
                  align="left"
                />
                <SortHead
                  field="value"
                  label="Valor"
                  filters={filters}
                  setFilters={setFilters}
                  align="left"
                />
                <RoiHead filters={filters} setFilters={setFilters} />
              </TableRow>
            </TableHeader>
            <TableBody>
              {groups.map((group) => (
                <GroupedRow
                  key={group.key}
                  group={group}
                  basis={roiBasis(filters)}
                  density={density}
                  onSelect={onSelect}
                />
              ))}
            </TableBody>
          </Table>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <SortHead field="name" label="Conjunto" filters={filters} setFilters={setFilters} />
                <SortHead field="theme" label="Tema" filters={filters} setFilters={setFilters} />
                <SortHead field="year" label="Ano" filters={filters} setFilters={setFilters} />
                <SortHead
                  field="storage"
                  label="Arrumação"
                  filters={filters}
                  setFilters={setFilters}
                />
                <SortHead field="state" label="Estado" filters={filters} setFilters={setFilters} />
                <SortHead
                  field="cost"
                  label="PVP / Pago"
                  filters={filters}
                  setFilters={setFilters}
                  align="right"
                />
                <SortHead
                  field="value"
                  label="Valor"
                  filters={filters}
                  setFilters={setFilters}
                  align="right"
                />
                <RoiHead filters={filters} setFilters={setFilters} />
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
                    <SetCell instance={instance} density={density} />
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
                    <div className="flex flex-col items-start gap-1">
                      {instance.build_state ? (
                        <Badge variant={BUILD_STATE_VARIANT}>
                          {BUILD_STATE_LABELS[instance.build_state]}
                        </Badge>
                      ) : null}
                      {instance.condition ? (
                        <Badge variant={CONDITION_VARIANTS[instance.condition]}>
                          {CONDITION_LABELS[instance.condition]}
                        </Badge>
                      ) : null}
                      {!instance.build_state && !instance.condition ? (
                        <span className="text-muted-foreground">—</span>
                      ) : null}
                    </div>
                  </TableCell>
                  <TableCell className="numeric text-right">
                    <CostCell
                      rrpEur={
                        instance.set_model?.rrp_eur ? Number(instance.set_model.rrp_eur) : null
                      }
                      paidEur={Number(instance.acquisition_cost_eur)}
                    />
                  </TableCell>
                  <TableCell className="numeric text-right">
                    <span className={instance.set_model?.value_is_stale ? 'text-warning' : ''}>
                      {eur(instance.current_value_eur)}
                    </span>
                  </TableCell>
                  <TableCell className="text-right">
                    <RoiCell instance={instance} basis={roiBasis(filters)} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>

      {data ? (
        <div className="flex flex-wrap items-center justify-between gap-4 text-sm">
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground">Linhas por página</span>
            <Select
              value={String(pageSize)}
              onValueChange={(value) => setFilters({ page_size: value, page: '1' })}
            >
              <SelectTrigger className="h-8 w-[4.5rem]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PAGE_SIZES.map((size) => (
                  <SelectItem key={size} value={size}>
                    {size}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <span className="text-muted-foreground">
              {data.total === 0
                ? 'sem resultados'
                : `${num((page - 1) * pageSize + 1)}–${num(Math.min(page * pageSize, data.total))} de ${num(data.total)}`}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => setFilters({ page: '1' })}
              aria-label="Primeira página"
            >
              <ChevronsLeft />
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => setFilters({ page: String(page - 1) })}
            >
              Anterior
            </Button>
            <span className="text-muted-foreground">
              {page} / {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => setFilters({ page: String(page + 1) })}
            >
              Seguinte
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => setFilters({ page: String(totalPages) })}
              aria-label="Última página"
            >
              <ChevronsRight />
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
