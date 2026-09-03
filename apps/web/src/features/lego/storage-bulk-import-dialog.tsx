import * as React from 'react';
import { FileSpreadsheet, Loader2 } from 'lucide-react';
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
import { useStorageBulkImport } from './api';

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
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  stepLabel?: string;
}) {
  const bulkImport = useStorageBulkImport();
  const [result, setResult] = React.useState<StorageBulkImportResult | null>(null);
  const [dragOver, setDragOver] = React.useState(false);
  const fileRef = React.useRef<HTMLInputElement>(null);

  React.useEffect(() => {
    if (!open) setResult(null);
  }, [open]);

  async function handleFile(file: File) {
    try {
      const response = await bulkImport.mutateAsync(file);
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
          {!result ? (
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
                disabled={bulkImport.isPending}
                className={cn(
                  'flex w-full flex-col items-center gap-3 rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground',
                  dragOver ? 'border-primary bg-primary/5' : 'border-input',
                )}
              >
                {bulkImport.isPending ? (
                  <Loader2 className="size-6 animate-spin" />
                ) : (
                  <FileSpreadsheet className="size-6" />
                )}
                <span>
                  {bulkImport.isPending
                    ? 'A importar…'
                    : 'Arraste um Excel (.xlsx), ou clique para escolher'}
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
          <Button onClick={() => onOpenChange(false)}>Fechar</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
