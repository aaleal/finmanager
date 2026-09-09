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
  isFs = true,
}: {
  receiptId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  isFs?: boolean;
}) {
  const addItem = useAddFsItem();
  const [description, setDescription] = React.useState('');
  const [value, setValue] = React.useState('');
  const [quantity, setQuantity] = React.useState('1');
  const [unit, setUnit] = React.useState('UN');
  const [lineNo, setLineNo] = React.useState('');

  React.useEffect(() => {
    if (open) {
      setDescription('');
      setValue('');
      setQuantity('1');
      setUnit('UN');
      setLineNo('');
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
        is_fs: isFs,
        line_no: isFs || !lineNo.trim() ? null : Math.round(Number(lineNo)),
      },
    });
    onOpenChange(false);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="sm">
        <DialogHeader>
          <DialogTitle>{isFs ? 'Adicionar artigo Fs' : 'Adicionar linha'}</DialogTitle>
        </DialogHeader>
        <DialogBody className="space-y-4">
          <p className="text-sm text-muted-foreground">
            {isFs
              ? 'Um artigo Fs nunca esteve na fatura: é acrescentado à mão e vale o seu valor nocional. Nenhum total impresso muda.'
              : 'Para uma linha que está no papel mas o leitor não apanhou. Entra na soma das linhas, portanto confirme a reconciliação depois de a acrescentar.'}
          </p>
          <Field label="Descrição">
            <Input value={description} onChange={(event) => setDescription(event.target.value)} />
          </Field>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label={isFs ? 'Valor nocional (€)' : 'PVP (€)'} className="sm:col-span-1">
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
          {!isFs ? (
            <Field
              label="N.º de linha"
              hint="Onde a linha está no talão. A grelha ordena-se por aqui; em branco fica no fim."
            >
              <Input
                type="number"
                min="1"
                step="1"
                inputMode="numeric"
                value={lineNo}
                onChange={(event) => setLineNo(event.target.value)}
              />
            </Field>
          ) : null}
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
