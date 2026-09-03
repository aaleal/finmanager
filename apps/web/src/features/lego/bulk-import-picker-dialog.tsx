import * as React from 'react';
import { Blocks, Boxes, LayoutGrid } from 'lucide-react';
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

export type BulkImportScope = 'all' | 'storage' | 'instances';

const OPTIONS: {
  value: BulkImportScope;
  icon: typeof LayoutGrid;
  label: string;
  hint: string;
}[] = [
  {
    value: 'all',
    icon: LayoutGrid,
    label: 'Tudo',
    hint: 'Arrumação e coleção (cópias), uma a seguir à outra.',
  },
  {
    value: 'storage',
    icon: Boxes,
    label: 'Só arrumação',
    hint: 'Áreas e contentores, folha «Arrumação» do ficheiro.',
  },
  {
    value: 'instances',
    icon: Blocks,
    label: 'Só coleção (cópias)',
    hint: 'Conjuntos e cópias físicas, folha «Cópias» do ficheiro.',
  },
];

/**
 * Middle step between the single «Importar em lote» button and the two
 * existing importers — picks which sheet(s) of the same workbook to read
 * instead of forcing two separate entry points into the module.
 */
export function BulkImportPickerDialog({
  open,
  onOpenChange,
  onPick,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onPick: (scope: BulkImportScope) => void;
}) {
  const [scope, setScope] = React.useState<BulkImportScope>('all');

  React.useEffect(() => {
    if (open) setScope('all');
  }, [open]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="sm">
        <DialogHeader>
          <DialogTitle>Importar em lote</DialogTitle>
          <DialogDescription>O que quer importar deste ficheiro?</DialogDescription>
        </DialogHeader>
        <DialogBody className="space-y-2">
          {OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => setScope(option.value)}
              className={cn(
                'flex w-full items-start gap-3 rounded-lg border p-3 text-left transition-colors',
                scope === option.value
                  ? 'border-primary bg-primary/5'
                  : 'border-input hover:bg-muted/50',
              )}
            >
              <option.icon className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
              <span>
                <span className="block text-sm font-medium">{option.label}</span>
                <span className="block text-xs text-muted-foreground">{option.hint}</span>
              </span>
            </button>
          ))}
        </DialogBody>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button
            onClick={() => {
              onOpenChange(false);
              onPick(scope);
            }}
          >
            Continuar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
