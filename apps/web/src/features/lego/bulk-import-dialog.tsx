import * as React from 'react';
import { Check, FileSpreadsheet, Loader2, X } from 'lucide-react';
import type { LegoBulkImportRow, LegoBulkImportRowResult, StorageLocation } from '@/lib/types';
import { Button } from '@/components/ui/button';
import { DateInput, Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/primitives';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useSession } from '@/features/auth/session';
import { cn } from '@/lib/utils';
import { useBulkImportCommit, useBulkImportPreview } from './api';
import { BUILD_STATE_LABELS, CONDITION_LABELS, SOURCE_LABELS } from './constants';

type Row = LegoBulkImportRow;

const NONE = '__none__';

function isRowValid(row: Row): boolean {
  return Object.keys(row.errors ?? {}).length === 0;
}

/** The spreadsheet's row 1 is always the header — `row_number` (used as the
 * stable key everywhere: progress map, retry, results) counts from there, but
 * showing that to the user makes the first data row look like "Linha 2". This
 * is a display-only offset; every lookup still keys off the real `row_number`. */
function displayRowNumber(rowNumber: number): number {
  return rowNumber - 1;
}

/** Same normalisation `toMoney` in `add-set-dialog.tsx` does — kept local since
 * that helper isn't exported and this is the only other place that needs it. */
function normalizeCost(value: unknown): string {
  const text = String(value ?? '')
    .trim()
    .replace(',', '.');
  const parsed = Number(text);
  return text && Number.isFinite(parsed) ? parsed.toFixed(2) : '0.00';
}

/**
 * Excel → preview table → commit, one Brickset lookup per row (M9.5).
 *
 * The table's "green" state is a client-side mirror of the same per-field
 * checks the preview endpoint runs (see docs/decisions/0048). Only the initial
 * upload and the final commit round-trip to the API; every edit in between is
 * local. See docs/decisions/0048-bulk-import-mirrors-the-export.md.
 */
export function BulkImportDialog({
  open,
  onOpenChange,
  storageLocations,
  stepLabel,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  storageLocations: StorageLocation[];
  stepLabel?: string;
}) {
  const { entities } = useSession();
  const writable = React.useMemo(
    () => entities.filter((entity) => !entity.is_readonly),
    [entities],
  );
  const preview = useBulkImportPreview();
  const commit = useBulkImportCommit();
  const [rows, setRows] = React.useState<Row[] | null>(null);
  const [results, setResults] = React.useState<LegoBulkImportRowResult[] | null>(null);
  // Row-by-row commit progress, filled live as the NDJSON stream comes in —
  // lets each row turn green/red as it's actually registered, instead of only
  // finding out once the whole batch is done.
  const [progress, setProgress] = React.useState<Map<number, LegoBulkImportRowResult>>(new Map());
  // Which rows will actually be sent to the server — defaults to "all", but the
  // user can uncheck rows they don't want imported without having to fix or
  // delete them from the spreadsheet.
  const [selected, setSelected] = React.useState<Set<number>>(new Set());
  const [dragOver, setDragOver] = React.useState(false);
  const fileRef = React.useRef<HTMLInputElement>(null);

  React.useEffect(() => {
    if (!open) {
      setRows(null);
      setResults(null);
      setProgress(new Map());
      setSelected(new Set());
    }
  }, [open]);

  async function handleFile(file: File) {
    try {
      const result = await preview.mutateAsync(file);
      setRows(result.rows);
      setSelected(new Set(result.rows.map((row) => row.row_number)));
    } catch {
      /* toasted by the hook */
    }
  }

  function toggleRow(rowNumber: number, checked: boolean) {
    setSelected((current) => {
      const next = new Set(current);
      if (checked) next.add(rowNumber);
      else next.delete(rowNumber);
      return next;
    });
  }

  function toggleAll(checked: boolean) {
    setSelected(checked ? new Set((rows ?? []).map((row) => row.row_number)) : new Set());
  }

  function patchRow(rowNumber: number, patch: Partial<Row>) {
    setRows((current) =>
      (current ?? []).map((row) => {
        if (row.row_number !== rowNumber) return row;
        const next: Row = { ...row, ...patch };
        const errors = { ...next.errors };
        for (const field of Object.keys(patch)) delete errors[field];
        if (!next.set_number?.trim()) errors.set_number = 'Indique o número do conjunto.';
        if (!next.entity_id) errors.entity_id = 'Indique a entidade.';
        if ('acquisition_cost_eur' in patch) {
          const normalized = String(next.acquisition_cost_eur ?? '')
            .trim()
            .replace(',', '.');
          if (normalized && Number.isNaN(Number(normalized))) {
            errors.acquisition_cost_eur = 'Custo inválido.';
          }
        }
        return { ...next, errors };
      }),
    );
  }

  const selectedRows = (rows ?? []).filter((row) => selected.has(row.row_number));
  const allValid = selectedRows.length > 0 && selectedRows.every(isRowValid);
  const failedCount = results?.filter((result) => !result.ok).length ?? 0;
  const allSelected = (rows ?? []).length > 0 && selected.size === rows!.length;
  const someSelected = selected.size > 0 && !allSelected;

  function onRowCommitted(result: LegoBulkImportRowResult) {
    setProgress((current) => new Map(current).set(result.row_number, result));
  }

  async function handleCommit() {
    if (!rows || selectedRows.length === 0) return;
    setProgress(new Map());
    const payload = selectedRows.map((row) => ({
      ...row,
      acquisition_cost_eur: normalizeCost(row.acquisition_cost_eur),
    }));
    const result = await commit.mutateAsync({ rows: payload, onRow: onRowCommitted });
    setResults(result);
  }

  // Resubmits only the rows that failed (e.g. Brickset was down) — never the
  // whole file again, since already-succeeded rows would just be duplicated
  // (instance rows have no natural key, unlike storage rows).
  async function handleRetryFailed() {
    if (!rows || !results) return;
    const failedNumbers = new Set(
      results.filter((result) => !result.ok).map((result) => result.row_number),
    );
    const payload = rows
      .filter((row) => failedNumbers.has(row.row_number))
      .map((row) => ({ ...row, acquisition_cost_eur: normalizeCost(row.acquisition_cost_eur) }));
    if (payload.length === 0) return;
    setProgress((current) => {
      const next = new Map(current);
      for (const rowNumber of failedNumbers) next.delete(rowNumber);
      return next;
    });
    const retried = await commit.mutateAsync({ rows: payload, onRow: onRowCommitted });
    const byRowNumber = new Map(retried.map((result) => [result.row_number, result]));
    setResults((current) =>
      (current ?? []).map((result) => byRowNumber.get(result.row_number) ?? result),
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="full">
        <DialogHeader>
          <DialogTitle>Importar em lote{stepLabel ? ` · ${stepLabel}` : ''}</DialogTitle>
          <DialogDescription>
            Uma linha por cópia física. O mesmo ficheiro que a «Exportar» produz serve de entrada —
            os dados do conjunto continuam a vir do Brickset, exatamente como no registo manual.
          </DialogDescription>
        </DialogHeader>

        <DialogBody className="space-y-4">
          {!rows && !results ? (
            <>
              <input
                ref={fileRef}
                type="file"
                accept=".xlsx"
                className="hidden"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  event.target.value = '';
                  if (file) void handleFile(file);
                }}
              />
              <button
                type="button"
                onClick={() => fileRef.current?.click()}
                onDragOver={(event) => {
                  event.preventDefault();
                  setDragOver(true);
                }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(event) => {
                  event.preventDefault();
                  setDragOver(false);
                  const file = event.dataTransfer.files?.[0];
                  if (file) void handleFile(file);
                }}
                disabled={preview.isPending}
                className={cn(
                  'flex w-full flex-col items-center gap-3 rounded-lg border border-dashed p-10 text-center text-sm text-muted-foreground',
                  dragOver ? 'border-primary bg-primary/5' : 'border-input',
                )}
              >
                {preview.isPending ? (
                  <Loader2 className="size-8 animate-spin" />
                ) : (
                  <FileSpreadsheet className="size-8" />
                )}
                <span>
                  {preview.isPending
                    ? 'A ler o ficheiro…'
                    : 'Arraste um Excel (.xlsx), ou clique para escolher'}
                </span>
                <span className="text-xs">
                  Número, Entidade, Área, Contentor, Estado, Condição, Origem, Custo, Data, Notas…
                </span>
              </button>
            </>
          ) : null}

          {rows && !results ? (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">
                {commit.isPending ? (
                  `A importar… ${progress.size} de ${selectedRows.length} processada(s).`
                ) : (
                  <>
                    {rows.length} linha(s), {selected.size} selecionada(s). Corrija as células
                    assinaladas — a importação só arranca quando todas as linhas selecionadas
                    estiverem certas.
                  </>
                )}
              </p>
              <div className="max-h-[50vh] overflow-y-auto rounded-lg border border-border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-8">
                        <Checkbox
                          checked={allSelected ? true : someSelected ? 'indeterminate' : false}
                          disabled={commit.isPending}
                          onCheckedChange={(value) => toggleAll(value !== false)}
                          aria-label="Selecionar todas as linhas"
                        />
                      </TableHead>
                      <TableHead>Linha</TableHead>
                      <TableHead>Conjunto</TableHead>
                      <TableHead>Entidade</TableHead>
                      <TableHead>Local</TableHead>
                      <TableHead>Estado</TableHead>
                      <TableHead>Condição</TableHead>
                      <TableHead>Origem</TableHead>
                      <TableHead>Custo (€)</TableHead>
                      <TableHead>Data</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {rows.map((row) => {
                      const status = progress.get(row.row_number);
                      const isSelected = selected.has(row.row_number);
                      return (
                        <TableRow
                          key={row.row_number}
                          className={cn(
                            status
                              ? status.ok
                                ? 'bg-success/10'
                                : 'bg-destructive/5'
                              : !isRowValid(row) && 'bg-destructive/5',
                            !isSelected && 'opacity-50',
                          )}
                        >
                          <TableCell>
                            <Checkbox
                              checked={isSelected}
                              disabled={commit.isPending}
                              onCheckedChange={(value) =>
                                toggleRow(row.row_number, value !== false)
                              }
                              aria-label={`Selecionar linha ${displayRowNumber(row.row_number)}`}
                            />
                          </TableCell>
                          <TableCell className="text-xs text-muted-foreground">
                            <span className="inline-flex items-center gap-1.5">
                              {displayRowNumber(row.row_number)}
                              {status ? (
                                status.ok ? (
                                  <Check className="size-3.5 text-success" />
                                ) : (
                                  <X className="size-3.5 text-destructive" />
                                )
                              ) : null}
                            </span>
                          </TableCell>
                          <TableCell>
                            <Input
                              value={row.set_number ?? ''}
                              disabled={commit.isPending}
                              className={cn(
                                'h-8 w-16',
                                row.errors?.set_number && 'border-destructive',
                              )}
                              onChange={(event) =>
                                patchRow(row.row_number, {
                                  set_number: event.target.value.toUpperCase(),
                                })
                              }
                            />
                          </TableCell>
                          <TableCell>
                            <Select
                              value={row.entity_id ?? ''}
                              disabled={commit.isPending}
                              onValueChange={(value) =>
                                patchRow(row.row_number, { entity_id: value })
                              }
                            >
                              <SelectTrigger
                                className={cn(
                                  'h-8 w-36',
                                  row.errors?.entity_id && 'border-destructive',
                                )}
                              >
                                <SelectValue placeholder={row.entity_name ?? '—'} />
                              </SelectTrigger>
                              <SelectContent>
                                {writable.map((entity) => (
                                  <SelectItem key={entity.id} value={entity.id}>
                                    {entity.name}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </TableCell>
                          <TableCell>
                            <Select
                              value={row.storage_location_id ?? NONE}
                              disabled={commit.isPending}
                              onValueChange={(value) =>
                                patchRow(row.row_number, {
                                  storage_location_id: value === NONE ? null : value,
                                })
                              }
                            >
                              <SelectTrigger
                                className={cn(
                                  'h-8 w-40',
                                  row.errors?.storage_location_id && 'border-destructive',
                                )}
                              >
                                <SelectValue
                                  placeholder={
                                    row.storage_area
                                      ? `${row.storage_area}${row.storage_container ? ` › ${row.storage_container}` : ''}`
                                      : '—'
                                  }
                                />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value={NONE}>—</SelectItem>
                                {storageLocations.map((location) => (
                                  <SelectItem key={location.id} value={location.id}>
                                    {location.label}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </TableCell>
                          <TableCell>
                            <Select
                              value={row.build_state ?? NONE}
                              disabled={commit.isPending}
                              onValueChange={(value) =>
                                patchRow(row.row_number, {
                                  build_state:
                                    value === NONE ? null : (value as Row['build_state']),
                                })
                              }
                            >
                              <SelectTrigger
                                className={cn(
                                  'h-8 w-32',
                                  row.errors?.build_state && 'border-destructive',
                                )}
                              >
                                <SelectValue placeholder="—" />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value={NONE}>—</SelectItem>
                                {Object.entries(BUILD_STATE_LABELS).map(([value, label]) => (
                                  <SelectItem key={value} value={value}>
                                    {label}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </TableCell>
                          <TableCell>
                            <Select
                              value={row.condition ?? NONE}
                              disabled={commit.isPending}
                              onValueChange={(value) =>
                                patchRow(row.row_number, {
                                  condition: value === NONE ? null : (value as Row['condition']),
                                })
                              }
                            >
                              <SelectTrigger
                                className={cn(
                                  'h-8 w-28',
                                  row.errors?.condition && 'border-destructive',
                                )}
                              >
                                <SelectValue placeholder="—" />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value={NONE}>—</SelectItem>
                                {Object.entries(CONDITION_LABELS).map(([value, label]) => (
                                  <SelectItem key={value} value={value}>
                                    {label}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </TableCell>
                          <TableCell>
                            <Select
                              value={row.acquisition_source ?? NONE}
                              disabled={commit.isPending}
                              onValueChange={(value) =>
                                patchRow(row.row_number, {
                                  acquisition_source:
                                    value === NONE ? null : (value as Row['acquisition_source']),
                                })
                              }
                            >
                              <SelectTrigger
                                className={cn(
                                  'h-8 w-28',
                                  row.errors?.acquisition_source && 'border-destructive',
                                )}
                              >
                                <SelectValue placeholder="—" />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value={NONE}>—</SelectItem>
                                {Object.entries(SOURCE_LABELS).map(([value, label]) => (
                                  <SelectItem key={value} value={value}>
                                    {label}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </TableCell>
                          <TableCell>
                            <Input
                              inputMode="decimal"
                              disabled={commit.isPending}
                              className={cn(
                                'h-8 w-20',
                                row.errors?.acquisition_cost_eur && 'border-destructive',
                              )}
                              value={String(row.acquisition_cost_eur ?? '')}
                              onChange={(event) =>
                                patchRow(row.row_number, {
                                  acquisition_cost_eur: event.target.value,
                                })
                              }
                            />
                          </TableCell>
                          <TableCell>
                            <DateInput
                              value={row.acquisition_date ?? ''}
                              disabled={commit.isPending}
                              onChange={(iso) =>
                                patchRow(row.row_number, { acquisition_date: iso || null })
                              }
                              className={cn(row.errors?.acquisition_date && 'border-destructive')}
                            />
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            </div>
          ) : null}

          {results ? (
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">
                {results.filter((result) => result.ok).length} de {results.length} cópia(s)
                registada(s).
              </p>
              <ul className="max-h-[50vh] divide-y divide-border overflow-y-auto rounded-lg border border-border text-sm">
                {results.map((result) => (
                  <li
                    key={result.row_number}
                    className="flex items-center justify-between gap-3 px-3 py-2"
                  >
                    <span className="text-muted-foreground">
                      Linha {displayRowNumber(result.row_number)}
                    </span>
                    <span className={cn(result.ok ? 'text-success' : 'text-destructive')}>
                      {result.message}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </DialogBody>

        <DialogFooter>
          {results ? (
            <>
              {failedCount > 0 ? (
                <Button variant="outline" loading={commit.isPending} onClick={handleRetryFailed}>
                  Tentar de novo ({failedCount})
                </Button>
              ) : null}
              <Button onClick={() => onOpenChange(false)}>Fechar</Button>
            </>
          ) : (
            <>
              <Button variant="ghost" onClick={() => onOpenChange(false)}>
                Cancelar
              </Button>
              {rows ? (
                <Button variant="outline" onClick={() => setRows(null)}>
                  Trocar ficheiro
                </Button>
              ) : null}
              {rows ? (
                <Button disabled={!allValid} loading={commit.isPending} onClick={handleCommit}>
                  Iniciar importação ({selected.size})
                </Button>
              ) : null}
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
