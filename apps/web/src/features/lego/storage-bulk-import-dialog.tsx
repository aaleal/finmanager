import * as React from 'react';
import { AlertTriangle, FileSpreadsheet, Loader2 } from 'lucide-react';
import type { StorageBulkImportResult } from '@/lib/types';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { cn } from '@/lib/utils';
import { useBulkCheckSheets, useStorageBulkImport } from './api';

/**
 * Excel → one-step upsert, no correction table (M9.5).
 *
 * Unlike the copies importer, a storage row is keyed on (área, contentor) and
 * safe to re-run: an existing location is updated in place, never duplicated —
 * see docs/decisions/0048-bulk-import-mirrors-the-export.md.
 */
export function StorageBulkImportDialog({
  open,
  onOpenChange,
  stepLabel,
  chained = false,
  onContinue,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  stepLabel?: string;
  /** True for the «Tudo» flow: the same workbook must also have collection
   * (cópias) data, checked upfront, and is handed to the next step via
   * `onContinue` instead of being asked for a second time. */
  chained?: boolean;
  onContinue?: (file: File) => void;
}) {
  const bulkImport = useStorageBulkImport();
  const checkSheets = useBulkCheckSheets();
  const [result, setResult] = React.useState<StorageBulkImportResult | null>(null);
  const [warning, setWarning] = React.useState<string | null>(null);
  const [importedFile, setImportedFile] = React.useState<File | null>(null);
  const [dragOver, setDragOver] = React.useState(false);
  const fileRef = React.useRef<HTMLInputElement>(null);
  const busy = bulkImport.isPending || checkSheets.isPending;

  React.useEffect(() => {
    if (!open) {
      setResult(null);
      setWarning(null);
      setImportedFile(null);
    }
  }, [open]);

  async function handleFile(file: File) {
    if (chained) {
      let check;
      try {
        check = await checkSheets.mutateAsync(file);
      } catch {
        return; // toasted by the hook
      }
      const missing: string[] = [];
      if (!check.has_storage) missing.push('arrumação');
      if (!check.has_instances) missing.push('coleção (cópias)');
      if (missing.length > 0) {
        setWarning(`O ficheiro não tem dados de ${missing.join(' nem de ')}.`);
        return;
      }
    }
    try {
      const response = await bulkImport.mutateAsync(file);
      setImportedFile(file);
      setResult(response);
    } catch {
      /* toasted by the hook */
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="sm">
        <DialogHeader>
          <DialogTitle>Importar locais em lote{stepLabel ? ` · ${stepLabel}` : ''}</DialogTitle>
          <DialogDescription>
            Um local por linha (área + contentor). O mesmo ficheiro que a «Exportar» produz, na
            folha «Arrumação», serve de entrada — um local já existente é atualizado, não duplicado.
          </DialogDescription>
        </DialogHeader>
        <DialogBody className="space-y-3">
          {warning ? (
            <div className="flex items-start gap-3 rounded-lg border border-destructive/50 bg-destructive/5 p-4 text-sm text-destructive">
              <AlertTriangle className="mt-0.5 size-5 shrink-0" />
              <p>{warning}</p>
            </div>
          ) : !result ? (
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
                disabled={busy}
                className={cn(
                  'flex w-full flex-col items-center gap-3 rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground',
                  dragOver ? 'border-primary bg-primary/5' : 'border-input',
                )}
              >
                {busy ? (
                  <Loader2 className="size-6 animate-spin" />
                ) : (
                  <FileSpreadsheet className="size-6" />
                )}
                <span>
                  {busy ? 'A importar…' : 'Arraste um Excel (.xlsx), ou clique para escolher'}
                </span>
              </button>
            </>
          ) : (
            <div className="space-y-2 text-sm">
              <p>
                {result.created} criado(s), {result.updated} atualizado(s).
              </p>
              {result.errors.length ? (
                <ul className="max-h-48 divide-y divide-border overflow-y-auto rounded-lg border border-border">
                  {result.errors.map((error) => (
                    <li
                      key={error.row_number}
                      className="flex justify-between gap-3 px-3 py-1.5 text-destructive"
                    >
                      <span>Linha {error.row_number}</span>
                      <span>{error.message}</span>
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          )}
        </DialogBody>
        <DialogFooter>
          {warning ? (
            <Button onClick={() => setWarning(null)}>Tentar outro ficheiro</Button>
          ) : chained && result && importedFile ? (
            <Button
              onClick={() => {
                onOpenChange(false);
                onContinue?.(importedFile);
              }}
            >
              Seguinte
            </Button>
          ) : (
            <Button onClick={() => onOpenChange(false)}>Fechar</Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
