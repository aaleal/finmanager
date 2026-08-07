import * as React from 'react';
import { useForm } from 'react-hook-form';
import { toast } from 'sonner';
import { ChevronDown, Link2, Search, Sparkles, X } from 'lucide-react';
import { ApiError } from '@/lib/api';
import type { LookupResult, StorageLocation, TransactionSuggestion } from '@/lib/types';
import { Button } from '@/components/ui/button';
import { Field, Input, Textarea } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Checkbox, Separator } from '@/components/ui/primitives';
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
import { TransactionPicker } from '@/components/transaction-picker';
import { useSession } from '@/features/auth/session';
import { useCreateInstance, useLookup, useStorageLocations } from './api';
import { BUILD_STATE_LABELS, CONDITION_LABELS, SOURCE_LABELS } from './constants';
import { cn } from '@/lib/utils';
import { date, eur } from '@/lib/format';

interface FormValues {
  set_number: string;
  is_custom: boolean;
  name: string;
  theme: string;
  subtheme: string;
  release_year: string;
  retired_year: string;
  piece_count: string;
  minifig_count: string;
  rrp_eur: string;
  current_value_eur: string;
  short_description: string;
  image_url: string;
  acquisition_date: string;
  acquisition_cost_eur: string;
  acquisition_source: string;
  storage_location_id: string;
  build_state: string;
  condition: string;
  has_box: boolean;
  has_instructions: boolean;
  missing_parts: string;
  notes: string;
}

const EMPTY: FormValues = {
  set_number: '',
  is_custom: false,
  name: '',
  theme: '',
  subtheme: '',
  release_year: '',
  retired_year: '',
  piece_count: '',
  minifig_count: '',
  rrp_eur: '',
  current_value_eur: '',
  short_description: '',
  image_url: '',
  acquisition_date: '',
  acquisition_cost_eur: '',
  acquisition_source: '',
  storage_location_id: '',
  build_state: '',
  condition: '',
  has_box: true,
  has_instructions: true,
  missing_parts: '',
  notes: '',
};

function toNumber(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
}

function toMoney(value: string) {
  const normalized = value.trim().replace(',', '.');
  if (!normalized) return null;
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed.toFixed(2) : null;
}

function Collapsible({
  title,
  children,
  defaultOpen = false,
}: {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = React.useState(defaultOpen);
  return (
    <div className="rounded-lg border border-border">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between px-4 py-2.5 text-sm font-medium"
      >
        {title}
        <ChevronDown className={cn('size-4 transition-transform', open && 'rotate-180')} />
      </button>
      {open ? <div className="space-y-4 border-t border-border px-4 py-4">{children}</div> : null}
    </div>
  );
}

export function AddSetDialog({
  open,
  onOpenChange,
  storageLocations,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  storageLocations: StorageLocation[];
}) {
  const form = useForm<FormValues>({ defaultValues: EMPTY });
  const lookup = useLookup();
  const createInstance = useCreateInstance();
  const { entities, activeEntityId } = useSession();
  const [entityId, setEntityId] = React.useState(activeEntityId ?? '');
  const [lookupResult, setLookupResult] = React.useState<LookupResult | null>(null);
  const [duplicateModelId, setDuplicateModelId] = React.useState<string | null>(null);
  const [pickerOpen, setPickerOpen] = React.useState(false);
  const [transaction, setTransaction] = React.useState<TransactionSuggestion | null>(null);

  const isCustom = form.watch('is_custom');
  const setNumber = form.watch('set_number');
  const writableEntities = entities.filter((entity) => !entity.is_readonly);

  React.useEffect(() => {
    if (!open) {
      form.reset(EMPTY);
      setLookupResult(null);
      setDuplicateModelId(null);
      setTransaction(null);
      setEntityId(activeEntityId ?? '');
    }
  }, [open, form, activeEntityId]);

  async function runLookup() {
    if (!setNumber.trim()) return;
    const result = await lookup.mutateAsync(setNumber.trim());
    setLookupResult(result);
    if (!result.found) return;

    // Pre-filled fields stay editable and manual edits are never overwritten.
    const apply = (field: keyof FormValues, value: string | number | null | undefined) => {
      if (value === null || value === undefined || value === '') return;
      if (form.getValues(field)) return;
      form.setValue(field, String(value) as never);
    };
    apply('name', result.name);
    apply('theme', result.theme);
    apply('subtheme', result.subtheme);
    apply('release_year', result.release_year);
    apply('retired_year', result.retired_year);
    apply('piece_count', result.piece_count);
    apply('minifig_count', result.minifig_count);
    apply('rrp_eur', result.rrp_eur);
    apply('image_url', result.image_url);
    apply('short_description', result.short_description);
  }

  async function onSubmit(values: FormValues) {
    setDuplicateModelId(null);
    const payload: Record<string, unknown> = {
      entity_id: entityId || undefined,
      acquisition_date: values.acquisition_date || null,
      acquisition_cost_eur: toMoney(values.acquisition_cost_eur) ?? '0.00',
      acquisition_source: values.acquisition_source || null,
      acquisition_transaction_id: transaction?.id ?? null,
      storage_location_id: values.storage_location_id || null,
      build_state: values.build_state || null,
      condition: values.condition || null,
      has_box: values.has_box,
      has_instructions: values.has_instructions,
      missing_parts: values.missing_parts || null,
      notes: values.notes || null,
      new_set: {
        set_number: values.is_custom ? null : values.set_number.trim().toUpperCase(),
        is_custom: values.is_custom,
        name: values.name.trim(),
        theme: values.theme || null,
        subtheme: values.subtheme || null,
        release_year: toNumber(values.release_year),
        retired_year: toNumber(values.retired_year),
        piece_count: toNumber(values.piece_count),
        minifig_count: toNumber(values.minifig_count),
        rrp_eur: toMoney(values.rrp_eur),
        current_value_eur: toMoney(values.current_value_eur),
        short_description: values.short_description || null,
        image_url: values.image_url || null,
      },
    };

    try {
      await createInstance.mutateAsync(payload);
      onOpenChange(false);
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        const modelId = (error.extra?.model_id as string | undefined) ?? null;
        setDuplicateModelId(modelId);
        toast.info('Este conjunto já existe — registe outra cópia a partir da coleção.');
      }
    }
  }

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent size="lg">
          <form onSubmit={form.handleSubmit(onSubmit)} className="flex min-h-0 flex-col">
            <DialogHeader>
              <DialogTitle>Adicionar conjunto</DialogTitle>
              <DialogDescription>
                Comece pelo número do conjunto. O mínimo necessário é o conjunto e o custo — tudo
                o resto é opcional.
              </DialogDescription>
            </DialogHeader>

            <DialogBody className="space-y-5">
              {/* --- Attribution ---------------------------------------------- */}
              {!activeEntityId ? (
                <Field
                  label="Entidade"
                  hint="A quem pertence esta cópia. Nunca é adivinhado quando está a ver «todas»."
                >
                  <Select value={entityId} onValueChange={setEntityId}>
                    <SelectTrigger>
                      <SelectValue placeholder="Escolher entidade…" />
                    </SelectTrigger>
                    <SelectContent>
                      {writableEntities.map((entity) => (
                        <SelectItem key={entity.id} value={entity.id}>
                          {entity.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>
              ) : null}

              {/* --- Identity ------------------------------------------------ */}
              <div className="space-y-3">
                <div className="flex flex-wrap items-end gap-3">
                  <Field label="Número do conjunto" className="min-w-[10rem] flex-1">
                    <Input
                      placeholder="10307"
                      disabled={isCustom}
                      autoFocus
                      {...form.register('set_number')}
                    />
                  </Field>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={runLookup}
                    loading={lookup.isPending}
                    disabled={isCustom || !setNumber.trim()}
                  >
                    <Search />
                    Procurar
                  </Button>
                </div>

                <label className="flex cursor-pointer items-center gap-2 text-sm text-muted-foreground">
                  <Checkbox
                    checked={isCustom}
                    onCheckedChange={(checked) => {
                      form.setValue('is_custom', checked === true);
                      if (checked === true) form.setValue('set_number', '');
                    }}
                  />
                  Não tem número / é um MOC
                </label>

                {lookupResult ? (
                  <div
                    className={cn(
                      'flex items-start gap-3 rounded-lg border px-3 py-2 text-sm',
                      lookupResult.found
                        ? 'border-success/30 bg-success/8 text-success'
                        : 'border-warning/30 bg-warning/8 text-warning',
                    )}
                  >
                    <Sparkles className="mt-0.5 size-4 shrink-0" />
                    <p>
                      {lookupResult.found
                        ? `Dados obtidos do Brickset para ${lookupResult.set_number}. Pode editar tudo.`
                        : lookupResult.message}
                    </p>
                  </div>
                ) : null}

                {duplicateModelId ? (
                  <div className="rounded-lg border border-primary/30 bg-primary/5 px-3 py-2 text-sm">
                    Já tem este conjunto. Feche esta janela e use{' '}
                    <strong>«adicionar outra cópia»</strong> na ficha do conjunto.
                  </div>
                ) : null}
              </div>

              <Separator />

              {/* --- Set metadata -------------------------------------------- */}
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Nome" className="sm:col-span-2">
                  <Input
                    placeholder="Torre Eiffel"
                    {...form.register('name', { required: true })}
                  />
                </Field>
                <Field label="Tema">
                  <Input placeholder="Icons" {...form.register('theme')} />
                </Field>
                <Field label="Subtema">
                  <Input placeholder="Landmarks" {...form.register('subtheme')} />
                </Field>
              </div>

              <Collapsible title="Detalhes do conjunto">
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field label="Ano de lançamento">
                    <Input type="number" {...form.register('release_year')} />
                  </Field>
                  <Field label="Ano de retirada" hint="Deixe vazio se ainda está à venda.">
                    <Input type="number" {...form.register('retired_year')} />
                  </Field>
                  <Field label="Peças">
                    <Input type="number" {...form.register('piece_count')} />
                  </Field>
                  <Field label="Minifiguras">
                    <Input type="number" {...form.register('minifig_count')} />
                  </Field>
                  <Field label="PVP original (€)">
                    <Input inputMode="decimal" placeholder="629,99" {...form.register('rrp_eur')} />
                  </Field>
                  <Field
                    label="Valor de mercado atual (€)"
                    hint="Mantido à mão. Fica marcado como desatualizado com o tempo."
                  >
                    <Input
                      inputMode="decimal"
                      placeholder="689,00"
                      {...form.register('current_value_eur')}
                    />
                  </Field>
                  <Field label="Descrição" className="sm:col-span-2">
                    <Textarea rows={2} {...form.register('short_description')} />
                  </Field>
                  <Field
                    label="Imagem (endereço)"
                    className="sm:col-span-2"
                    hint="A imagem é transferida uma vez e guardada no NAS — nunca é usada por ligação direta."
                  >
                    <Input placeholder="https://…" {...form.register('image_url')} />
                  </Field>
                </div>
              </Collapsible>

              <Separator />

              {/* --- The copy ------------------------------------------------- */}
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Custo de aquisição (€)" hint="0 para prendas — o ROI fica «—».">
                  <Input
                    inputMode="decimal"
                    placeholder="599,99"
                    {...form.register('acquisition_cost_eur')}
                  />
                </Field>
                <Field label="Data de aquisição">
                  <Input type="date" {...form.register('acquisition_date')} />
                </Field>
                <Field label="Origem">
                  <Select
                    value={form.watch('acquisition_source')}
                    onValueChange={(value) => form.setValue('acquisition_source', value)}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="—" />
                    </SelectTrigger>
                    <SelectContent>
                      {Object.entries(SOURCE_LABELS).map(([value, label]) => (
                        <SelectItem key={value} value={value}>
                          {label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>
                <Field label="Local de arrumação">
                  <Select
                    value={form.watch('storage_location_id')}
                    onValueChange={(value) => form.setValue('storage_location_id', value)}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="—" />
                    </SelectTrigger>
                    <SelectContent>
                      {storageLocations.map((location) => (
                        <SelectItem key={location.id} value={location.id}>
                          {location.label}
                          {location.is_full ? ' · cheio' : ''}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>
                <Field label="Estado de construção">
                  <Select
                    value={form.watch('build_state')}
                    onValueChange={(value) => form.setValue('build_state', value)}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="—" />
                    </SelectTrigger>
                    <SelectContent>
                      {Object.entries(BUILD_STATE_LABELS).map(([value, label]) => (
                        <SelectItem key={value} value={value}>
                          {label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>
                <Field label="Condição">
                  <Select
                    value={form.watch('condition')}
                    onValueChange={(value) => form.setValue('condition', value)}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="—" />
                    </SelectTrigger>
                    <SelectContent>
                      {Object.entries(CONDITION_LABELS).map(([value, label]) => (
                        <SelectItem key={value} value={value}>
                          {label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>
              </div>

              <Collapsible title="Estado, peças em falta e notas">
                <div className="flex flex-wrap gap-5">
                  <label className="flex cursor-pointer items-center gap-2 text-sm">
                    <Checkbox
                      checked={form.watch('has_box')}
                      onCheckedChange={(checked) => form.setValue('has_box', checked === true)}
                    />
                    Tem caixa original
                  </label>
                  <label className="flex cursor-pointer items-center gap-2 text-sm">
                    <Checkbox
                      checked={form.watch('has_instructions')}
                      onCheckedChange={(checked) =>
                        form.setValue('has_instructions', checked === true)
                      }
                    />
                    Tem instruções
                  </label>
                </div>
                <Field
                  label="Peças em falta"
                  hint="Texto livre. Marca a cópia como incompleta e não altera o valor."
                >
                  <Textarea
                    rows={2}
                    placeholder="2x 3001 vermelho, 1x canopy"
                    {...form.register('missing_parts')}
                  />
                </Field>
                <Field label="Notas desta cópia">
                  <Textarea rows={2} {...form.register('notes')} />
                </Field>
              </Collapsible>

              <div className="flex items-center justify-between gap-3 rounded-lg border border-border px-4 py-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium">Movimento bancário</p>
                  {transaction ? (
                    <p className="truncate text-xs text-muted-foreground">
                      {date(transaction.booked_date)} · {transaction.description} ·{' '}
                      {eur(transaction.amount_eur)}
                    </p>
                  ) : (
                    <p className="text-xs text-muted-foreground">
                      Opcional — ligue esta compra à linha do extrato.
                    </p>
                  )}
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  {transaction ? (
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      onClick={() => setTransaction(null)}
                    >
                      <X />
                    </Button>
                  ) : null}
                  <Button type="button" variant="outline" size="sm" onClick={() => setPickerOpen(true)}>
                    <Link2 />
                    Escolher
                  </Button>
                </div>
              </div>
            </DialogBody>

            <DialogFooter>
              <div className="mr-auto hidden items-center gap-2 sm:flex">
                {isCustom ? <Badge variant="secondary">MOC</Badge> : null}
              </div>
              <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
                Cancelar
              </Button>
              <Button type="submit" loading={createInstance.isPending} disabled={!entityId}>
                Guardar cópia
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <TransactionPicker
        open={pickerOpen}
        onOpenChange={setPickerOpen}
        nearDate={form.watch('acquisition_date') || null}
        amountEur={toMoney(form.watch('acquisition_cost_eur'))}
        onSelect={setTransaction}
      />
    </>
  );
}

export function AddCopyDialog({
  open,
  onOpenChange,
  modelId,
  modelName,
  entityId,
  storageLocations,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  modelId: string;
  modelName: string;
  entityId: string;
  storageLocations: StorageLocation[];
}) {
  const createInstance = useCreateInstance();
  const form = useForm<Pick<FormValues, 'acquisition_cost_eur' | 'acquisition_date' | 'acquisition_source' | 'storage_location_id' | 'build_state' | 'condition' | 'notes'>>({
    defaultValues: {
      acquisition_cost_eur: '',
      acquisition_date: '',
      acquisition_source: '',
      storage_location_id: '',
      build_state: '',
      condition: '',
      notes: '',
    },
  });

  React.useEffect(() => {
    if (!open) form.reset();
  }, [open, form]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="sm">
        <form
          onSubmit={form.handleSubmit(async (values) => {
            await createInstance.mutateAsync({
              lego_set_model_id: modelId,
              entity_id: entityId,
              acquisition_cost_eur: toMoney(values.acquisition_cost_eur) ?? '0.00',
              acquisition_date: values.acquisition_date || null,
              acquisition_source: values.acquisition_source || null,
              storage_location_id: values.storage_location_id || null,
              build_state: values.build_state || null,
              condition: values.condition || null,
              notes: values.notes || null,
            });
            onOpenChange(false);
          })}
        >
          <DialogHeader>
            <DialogTitle>Adicionar outra cópia</DialogTitle>
            <DialogDescription>{modelName}</DialogDescription>
          </DialogHeader>
          <DialogBody className="grid gap-4 sm:grid-cols-2">
            <Field label="Custo (€)">
              <Input inputMode="decimal" {...form.register('acquisition_cost_eur')} />
            </Field>
            <Field label="Data">
              <Input type="date" {...form.register('acquisition_date')} />
            </Field>
            <Field label="Origem">
              <Select
                value={form.watch('acquisition_source')}
                onValueChange={(value) => form.setValue('acquisition_source', value)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="—" />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(SOURCE_LABELS).map(([value, label]) => (
                    <SelectItem key={value} value={value}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field label="Local">
              <Select
                value={form.watch('storage_location_id')}
                onValueChange={(value) => form.setValue('storage_location_id', value)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="—" />
                </SelectTrigger>
                <SelectContent>
                  {storageLocations.map((location) => (
                    <SelectItem key={location.id} value={location.id}>
                      {location.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field label="Estado">
              <Select
                value={form.watch('build_state')}
                onValueChange={(value) => form.setValue('build_state', value)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="—" />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(BUILD_STATE_LABELS).map(([value, label]) => (
                    <SelectItem key={value} value={value}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field label="Condição">
              <Select
                value={form.watch('condition')}
                onValueChange={(value) => form.setValue('condition', value)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="—" />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(CONDITION_LABELS).map(([value, label]) => (
                    <SelectItem key={value} value={value}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field label="Notas" className="sm:col-span-2">
              <Textarea rows={2} {...form.register('notes')} />
            </Field>
          </DialogBody>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" loading={createInstance.isPending}>
              Adicionar
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export { useStorageLocations };
