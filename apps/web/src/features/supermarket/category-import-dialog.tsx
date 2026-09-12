import * as React from 'react';
import { FileSpreadsheet, Loader2 } from 'lucide-react';
import type { CategoryImportResult } from '@/lib/types';
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
import { useImportCategories } from './catalogue-api';

/**
 * Excel → one-step ensure, no correction table (mirrors the LEGO storage
 * importer). Additive only: a name already in the tree, at the same level and
 * under the same parent, is left untouched — see docs/decisions/0056.
 */
export function CategoryImportDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const bulkImport = useImportCategories();
  const [result, setResult] = React.useState<CategoryImportResult | null>(null);
  const [dragOver, setDragOver] = React.useState(false);
  const fileRef = React.useRef<HTMLInputElement>(null);
  const busy = bulkImport.isPending;

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
          <DialogTitle>Importar categorias</DialogTitle>
          <DialogDescription>
            Um caminho por linha (Nível 1, Nível 2, Nível 3). O ficheiro que a «Exportar» produz
            serve de entrada — uma categoria já existente não é alterada, só a que falta é criada.
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
                {result.created} criada(s), {result.existing} já existente(s).
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
