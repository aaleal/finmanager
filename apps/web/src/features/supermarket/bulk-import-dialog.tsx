import * as React from 'react';
import { Check, FileSpreadsheet, Loader2, X } from 'lucide-react';
import type { BulkProductImportRow, BulkProductImportRowResult, CategoryResult } from '@/lib/types';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Checkbox, Switch } from '@/components/ui/primitives';
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
import { cn } from '@/lib/utils';
import { CategoryPicker } from './category-picker';
import { AttributeBadges } from './product-attributes';
import { useBulkProductImportCommit, useBulkProductImportPreview } from './catalogue-api';

type Row = BulkProductImportRow;

const ATTRIBUTE_ERROR_FIELDS = ['conservation', 'presentation', 'dietary_attributes'] as const;

/** The spreadsheet's row 1 is always the header — `row_number` counts from
 * there, but showing that verbatim makes the first data row look like "Linha
 * 2". Display-only offset; every lookup still keys off the real `row_number`. */
function displayRowNumber(rowNumber: number): number {
  return rowNumber - 1;
}

function isRowValid(row: Row): boolean {
  return Object.keys(row.errors ?? {}).length === 0;
}

/**
 * Excel → preview table → commit, one row per curated product (no per-row
 * external lookup — unlike LEGO's Brickset call, this never touches the
 * network beyond the two round-trips below).
 */
export function BulkImportDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const preview = useBulkProductImportPreview();
  const commit = useBulkProductImportCommit();
  const [rows, setRows] = React.useState<Row[] | null>(null);
  const [results, setResults] = React.useState<BulkProductImportRowResult[] | null>(null);
  const [selected, setSelected] = React.useState<Set<number>>(new Set());
  const [dragOver, setDragOver] = React.useState(false);
  const fileRef = React.useRef<HTMLInputElement>(null);

  React.useEffect(() => {
    if (!open) {
      setRows(null);
      setResults(null);
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
        if (!next.canonical_name?.trim()) errors.canonical_name = 'Indique o nome do produto.';
        return { ...next, errors };
      }),
    );
  }

  const selectedRows = (rows ?? []).filter((row) => selected.has(row.row_number));
  const allValid = selectedRows.length > 0 && selectedRows.every(isRowValid);
  const failedCount = results?.filter((result) => !result.ok).length ?? 0;
  const allSelected = (rows ?? []).length > 0 && selected.size === rows!.length;
  const someSelected = selected.size > 0 && !allSelected;

  async function handleCommit() {
    if (!rows || selectedRows.length === 0) return;
    const result = await commit.mutateAsync(selectedRows);
    setResults(result);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="full">
        <DialogHeader>
          <DialogTitle>Importar produtos em lote</DialogTitle>
          <DialogDescription>
            Uma linha por produto já curado. Um produto que já exista (mesmo nome e marca) é
            ignorado, nunca duplicado.
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
                  Nome, Marca, Categoria (ou Cat1/Cat2/Cat3), Vendido a peso, Formatos (kg), Marca
                  branca, Conservação, Corte, Tags…
                </span>
              </button>
            </>
          ) : null}

          {rows && !results ? (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">
                {rows.length} linha(s), {selected.size} selecionada(s). Corrija as células
                assinaladas — a importação só arranca quando todas as linhas selecionadas estiverem
                certas.
              </p>
              <div className="max-h-[55vh] overflow-y-auto rounded-lg border border-border">
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
                      <TableHead>Nome</TableHead>
                      <TableHead>Marca</TableHead>
                      <TableHead>Categoria</TableHead>
                      <TableHead className="text-center">A peso</TableHead>
                      <TableHead>Formatos</TableHead>
                      <TableHead>Atributos</TableHead>
                      <TableHead>Estado</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {rows.map((row) => {
                      const valid = isRowValid(row);
                      const isSelected = selected.has(row.row_number);
                      return (
                        <TableRow key={row.row_number} className={cn(!valid && 'bg-destructive/5')}>
                          <TableCell>
                            <Checkbox
                              checked={isSelected}
                              disabled={commit.isPending}
                              onCheckedChange={(value) => toggleRow(row.row_number, value === true)}
                              aria-label={`Selecionar linha ${displayRowNumber(row.row_number)}`}
                            />
                          </TableCell>
                          <TableCell>
                            <Badge variant="muted">{displayRowNumber(row.row_number)}</Badge>
                          </TableCell>
                          <TableCell>
                            <Input
                              disabled={commit.isPending}
                              value={row.canonical_name ?? ''}
                              onChange={(event) =>
                                patchRow(row.row_number, { canonical_name: event.target.value })
                              }
                              className={cn(row.errors?.canonical_name && 'border-destructive')}
                            />
                          </TableCell>
                          <TableCell>
                            <Input
                              disabled={commit.isPending}
                              value={row.brand ?? ''}
                              onChange={(event) =>
                                patchRow(row.row_number, { brand: event.target.value || null })
                              }
                            />
                          </TableCell>
                          <TableCell className="min-w-56">
                            <CategoryPicker
                              disabled={commit.isPending}
                              value={row.category_path ?? null}
                              allowClear
                              onSelect={(category: CategoryResult | null) =>
                                patchRow(row.row_number, {
                                  category_id: category?.id ?? null,
                                  category_path: category?.path ?? null,
                                })
                              }
                            />
                          </TableCell>
                          <TableCell className="text-center">
                            <Switch
                              disabled={commit.isPending}
                              checked={row.sold_by_weight}
                              onCheckedChange={(value) =>
                                patchRow(row.row_number, { sold_by_weight: value })
                              }
                            />
                          </TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            {row.pack_weights_kg?.length
                              ? row.pack_weights_kg.map((weight) => `${weight} kg`).join(', ')
                              : '—'}
                            {row.errors?.pack_weights ? (
                              <p className="text-xs text-destructive">{row.errors.pack_weights}</p>
                            ) : null}
                          </TableCell>
                          <TableCell className="min-w-40">
                            <AttributeBadges
                              isOwnBrand={row.is_own_brand}
                              conservation={row.conservation}
                              presentation={row.presentation}
                              dietary={row.dietary_attributes}
                            />
                            {ATTRIBUTE_ERROR_FIELDS.map((field) =>
                              row.errors?.[field] ? (
                                <p key={field} className="text-xs text-destructive">
                                  {row.errors[field]}
                                </p>
                              ) : null,
                            )}
                          </TableCell>
                          <TableCell>
                            {row.existing_product_id ? (
                              <Badge variant="warning">já existe</Badge>
                            ) : valid ? (
                              <Badge variant="success">novo</Badge>
                            ) : (
                              <Badge variant="destructive">por corrigir</Badge>
                            )}
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
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">
                {results.length - failedCount} de {results.length} linha(s) processada(s) com
                sucesso.
                {failedCount ? ` ${failedCount} falharam.` : ''}
              </p>
              <div className="max-h-[55vh] overflow-y-auto rounded-lg border border-border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-8" />
                      <TableHead>Linha</TableHead>
                      <TableHead>Mensagem</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {results.map((result) => (
                      <TableRow
                        key={result.row_number}
                        className={result.ok ? 'bg-success/10' : 'bg-destructive/5'}
                      >
                        <TableCell>
                          {result.ok ? (
                            <Check className="size-4 text-success" />
                          ) : (
                            <X className="size-4 text-destructive" />
                          )}
                        </TableCell>
                        <TableCell>
                          <Badge variant="muted">{displayRowNumber(result.row_number)}</Badge>
                        </TableCell>
                        <TableCell className="text-sm">{result.message}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </div>
          ) : null}
        </DialogBody>

        <DialogFooter>
          {rows && !results ? (
            <>
              <Button variant="ghost" onClick={() => onOpenChange(false)}>
                Cancelar
              </Button>
              <Button
                disabled={!allValid || commit.isPending}
                loading={commit.isPending}
                onClick={handleCommit}
              >
                Importar {selected.size} linha(s)
              </Button>
            </>
          ) : (
            <Button onClick={() => onOpenChange(false)}>{results ? 'Fechar' : 'Cancelar'}</Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
