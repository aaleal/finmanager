import * as React from 'react';
import { Plus, Scale } from 'lucide-react';
import type { CategoryResult, MasterProduct } from '@/lib/types';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Field, Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/primitives';
import { CategoryPicker } from './category-picker';
import {
  ProductAttributeFields,
  emptyAttributes,
  type ProductAttributes,
} from './product-attributes';
import { useCreateProduct } from './catalogue-api';

/**
 * Create a `MasterProduct` without leaving the screen you are on.
 *
 * Shared on purpose: the catalogue manager and the receipt review pane open the
 * very same dialog, so correcting a line during review never means abandoning a
 * half-reviewed invoice to go and create a product elsewhere (FR-1.2, UX-1.2).
 */
export function ProductCreateDialog({
  open,
  onOpenChange,
  initialName = '',
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialName?: string;
  onCreated?: (product: MasterProduct) => void;
}) {
  const create = useCreateProduct();
  const [name, setName] = React.useState(initialName);
  const [brand, setBrand] = React.useState('');
  const [category, setCategory] = React.useState<CategoryResult | null>(null);
  const [soldByWeight, setSoldByWeight] = React.useState(false);
  const [attributes, setAttributes] = React.useState<ProductAttributes>(emptyAttributes);

  React.useEffect(() => {
    if (open) {
      setName(initialName);
      setBrand('');
      setCategory(null);
      setSoldByWeight(false);
      setAttributes(emptyAttributes());
    }
  }, [open, initialName]);

  const valid = name.trim().length > 0;

  async function submit() {
    if (!valid) return;
    const product = await create.mutateAsync({
      canonical_name: name.trim(),
      brand: brand.trim() || null,
      category_id: category?.id ?? null,
      sold_by_weight: soldByWeight,
      ...attributes,
    });
    onOpenChange(false);
    onCreated?.(product);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="sm">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Plus className="size-4" />
            Novo produto
          </DialogTitle>
        </DialogHeader>
        <DialogBody className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Dois artigos com categorias diferentes são, por regra, produtos diferentes — a categoria
            vive aqui e não na linha da fatura.
          </p>
          <Field label="Nome canónico" hint="O nome que passa a aparecer em todo o lado.">
            <Input autoFocus value={name} onChange={(event) => setName(event.target.value)} />
          </Field>
          <Field label="Marca">
            <Input value={brand} onChange={(event) => setBrand(event.target.value)} />
          </Field>
          <Field label="Categoria" hint="Caminho completo L1 › L2 › L3.">
            <CategoryPicker value={category?.path ?? null} onSelect={setCategory} />
          </Field>
          <div className="flex items-center justify-between rounded-lg border border-border px-3 py-2">
            <div className="flex items-center gap-2 text-sm">
              <Scale className="size-4 text-muted-foreground" />
              Vendido a peso
            </div>
            <Switch checked={soldByWeight} onCheckedChange={setSoldByWeight} />
          </div>
          <ProductAttributeFields value={attributes} onChange={setAttributes} />
        </DialogBody>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button disabled={!valid} loading={create.isPending} onClick={submit}>
            Criar produto
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
