import * as React from 'react';
import { Field, Input } from '@/components/ui/input';
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { UNIT_OPTIONS } from './constants';
import { useAddFsItem } from './api';

export function AddFsItemDialog({
  receiptId,
  open,
  onOpenChange,
}: {
  receiptId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const addItem = useAddFsItem();
  const [description, setDescription] = React.useState('');
  const [value, setValue] = React.useState('');
  const [quantity, setQuantity] = React.useState('1');
  const [unit, setUnit] = React.useState('UN');

  React.useEffect(() => {
    if (open) {
      setDescription('');
      setValue('');
      setQuantity('1');
      setUnit('UN');
    }
  }, [open]);

  const numericValue = Number(value.replace(',', '.'));
  const numericQuantity = Number(quantity.replace(',', '.'));
  const valid = description.trim().length > 0 && numericValue > 0 && numericQuantity > 0;

  async function submit() {
    if (!valid) return;
    await addItem.mutateAsync({
      receiptId,
      body: {
        description_raw: description.trim(),
        unit_price_pvp_eur: numericValue,
        quantity: numericQuantity,
        unit,
      },
    });
    onOpenChange(false);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="sm">
        <DialogHeader>
          <DialogTitle>Adicionar artigo Fs</DialogTitle>
        </DialogHeader>
        <DialogBody className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Um artigo Fs nunca esteve na fatura: é acrescentado à mão e vale o seu valor
            nocional. Nenhum total impresso muda.
          </p>
          <Field label="Descrição">
            <Input value={description} onChange={(event) => setDescription(event.target.value)} />
          </Field>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Valor nocional (€)" className="sm:col-span-1">
              <Input
                type="number"
                step="0.01"
                min="0.01"
                inputMode="decimal"
                value={value}
                onChange={(event) => setValue(event.target.value)}
              />
            </Field>
            <Field label="Quantidade">
              <Input
                type="number"
                step="0.01"
                min="0"
                inputMode="decimal"
                value={quantity}
                onChange={(event) => setQuantity(event.target.value)}
              />
            </Field>
            <Field label="Unidade">
              <Select value={unit} onValueChange={setUnit}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {UNIT_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
          </div>
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button disabled={!valid} loading={addItem.isPending} onClick={submit}>
            Adicionar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
