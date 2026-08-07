import * as React from 'react';
import {
  AlertTriangle,
  Blocks,
  Boxes,
  ExternalLink,
  Image as ImageIcon,
  Link2,
  PencilLine,
  Plus,
  Trash2,
} from 'lucide-react';
import type { LegoSetInstance, StorageLocation, TransactionSuggestion } from '@/lib/types';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Field, Input, Textarea } from '@/components/ui/input';
import { Checkbox, Separator, Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/primitives';
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
  DialogFooter,
  DialogHeader,
  DialogTitle,
  SheetContent,
} from '@/components/ui/dialog';
import { DetailRow } from '@/components/ui/feedback';
import { TransactionPicker } from '@/components/transaction-picker';
import { date, eur, num, percent, relativeDays, signedEur, toDateInput } from '@/lib/format';
import { cn } from '@/lib/utils';
import { useSession } from '@/features/auth/session';
import {
  useDeleteInstance,
  useModelInstances,
  useSetInstancePhoto,
  useUpdateInstance,
  useUpdateModel,
} from './api';
import {
  BUILD_STATE_LABELS,
  CONDITION_LABELS,
  CONDITION_VARIANTS,
  OWNERSHIP_LABELS,
  SOURCE_LABELS,
  externalLinks,
} from './constants';
import { AddCopyDialog } from './add-set-dialog';

function money(value: string) {
  const normalized = value.trim().replace(',', '.');
  if (!normalized) return null;
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed.toFixed(2) : null;
}

function RoiPill({ instance }: { instance: LegoSetInstance }) {
  if (instance.roi_pct === null) {
    return (
      <Badge variant="muted" title="Sem base de custo ou sem valor definido">
        ROI —
      </Badge>
    );
  }
  const positive = Number(instance.roi_pct) >= 0;
  return (
    <Badge variant={positive ? 'success' : 'destructive'}>
      {percent(instance.roi_pct)} · {signedEur(instance.appreciation_eur)}
    </Badge>
  );
}

function ValueEditor({ instance }: { instance: LegoSetInstance }) {
  const model = instance.set_model;
  const updateModel = useUpdateModel();
  const [editing, setEditing] = React.useState(false);
  const [value, setValue] = React.useState(model?.current_value_eur ?? '');

  if (!model) return null;

  if (!editing) {
    return (
      <div className="space-y-1">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="numeric text-2xl font-semibold">{eur(model.current_value_eur)}</p>
            <p className="text-xs text-muted-foreground">
              {model.current_value_eur
                ? `atualizado ${relativeDays(model.value_updated_at)}`
                : 'sem valor definido'}
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
            <PencilLine />
            Atualizar valor
          </Button>
        </div>
        {model.value_is_stale && model.current_value_eur ? (
          <p className="flex items-center gap-1.5 text-xs font-medium text-warning">
            <AlertTriangle className="size-3.5" />
            Valor possivelmente desatualizado.
          </p>
        ) : null}
      </div>
    );
  }

  return (
    <div className="flex items-end gap-2">
      <Field label="Valor de mercado (€)" className="flex-1">
        <Input
          autoFocus
          inputMode="decimal"
          value={value}
          onChange={(event) => setValue(event.target.value)}
        />
      </Field>
      <Button
        size="sm"
        loading={updateModel.isPending}
        onClick={async () => {
          await updateModel.mutateAsync({ id: model.id, current_value_eur: money(value) });
          setEditing(false);
        }}
      >
        Guardar
      </Button>
      <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
        Cancelar
      </Button>
    </div>
  );
}

function OwnershipControls({ instance }: { instance: LegoSetInstance }) {
  const update = useUpdateInstance();
  const [status, setStatus] = React.useState(instance.ownership_status);
  const [salePrice, setSalePrice] = React.useState(instance.sale_price_eur ?? '');
  const [saleDate, setSaleDate] = React.useState(toDateInput(instance.sale_date));

  const changed =
    status !== instance.ownership_status ||
    salePrice !== (instance.sale_price_eur ?? '') ||
    saleDate !== toDateInput(instance.sale_date);

  return (
    <div className="space-y-3">
      <Field label="Estado de propriedade">
        <Select value={status} onValueChange={(value) => setStatus(value as typeof status)}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {Object.entries(OWNERSHIP_LABELS).map(([value, label]) => (
              <SelectItem key={value} value={value}>
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>

      {status !== 'IN_COLLECTION' ? (
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Valor de venda (€)" hint="Opcional. Nunca entra no cálculo do ROI.">
            <Input
              inputMode="decimal"
              value={salePrice}
              onChange={(event) => setSalePrice(event.target.value)}
            />
          </Field>
          <Field label="Data">
            <Input type="date" value={saleDate} onChange={(event) => setSaleDate(event.target.value)} />
          </Field>
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">
          Voltar a «Na coleção» apaga o registo de venda.
        </p>
      )}

      <Button
        size="sm"
        disabled={!changed}
        loading={update.isPending}
        onClick={() =>
          update.mutate({
            id: instance.id,
            ownership_status: status,
            sale_price_eur: status === 'IN_COLLECTION' ? null : money(salePrice),
            sale_date: status === 'IN_COLLECTION' ? null : saleDate || null,
          })
        }
      >
        Guardar estado
      </Button>
    </div>
  );
}

function EditCopyForm({
  instance,
  storageLocations,
}: {
  instance: LegoSetInstance;
  storageLocations: StorageLocation[];
}) {
  const update = useUpdateInstance();
  const [pickerOpen, setPickerOpen] = React.useState(false);
  const [form, setForm] = React.useState({
    acquisition_cost_eur: instance.acquisition_cost_eur,
    acquisition_date: toDateInput(instance.acquisition_date),
    acquisition_source: instance.acquisition_source ?? '',
    storage_location_id: instance.storage_location_id ?? '',
    build_state: instance.build_state ?? '',
    condition: instance.condition ?? '',
    has_box: instance.has_box,
    has_instructions: instance.has_instructions,
    missing_parts: instance.missing_parts ?? '',
    notes: instance.notes ?? '',
  });

  const selectedLocation = storageLocations.find(
    (location) => location.id === form.storage_location_id,
  );

  function set<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((previous) => ({ ...previous, [key]: value }));
  }

  return (
    <>
      <div className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Custo (€)">
            <Input
              inputMode="decimal"
              value={form.acquisition_cost_eur}
              onChange={(event) => set('acquisition_cost_eur', event.target.value)}
            />
          </Field>
          <Field label="Data de aquisição">
            <Input
              type="date"
              value={form.acquisition_date}
              onChange={(event) => set('acquisition_date', event.target.value)}
            />
          </Field>
          <Field label="Origem">
            <Select
              value={form.acquisition_source}
              onValueChange={(value) => set('acquisition_source', value)}
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
          <Field
            label="Local de arrumação"
            error={selectedLocation?.is_full ? 'Este local está marcado como cheio.' : undefined}
          >
            <Select
              value={form.storage_location_id}
              onValueChange={(value) => set('storage_location_id', value)}
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
            <Select value={form.build_state} onValueChange={(value) => set('build_state', value)}>
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
            <Select value={form.condition} onValueChange={(value) => set('condition', value)}>
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

        <div className="flex flex-wrap gap-5">
          <label className="flex cursor-pointer items-center gap-2 text-sm">
            <Checkbox
              checked={form.has_box}
              onCheckedChange={(checked) => set('has_box', checked === true)}
            />
            Tem caixa
          </label>
          <label className="flex cursor-pointer items-center gap-2 text-sm">
            <Checkbox
              checked={form.has_instructions}
              onCheckedChange={(checked) => set('has_instructions', checked === true)}
            />
            Tem instruções
          </label>
        </div>

        <Field label="Peças em falta" hint="Texto livre; não altera o valor de mercado.">
          <Textarea
            rows={2}
            value={form.missing_parts}
            onChange={(event) => set('missing_parts', event.target.value)}
          />
        </Field>

        <Field label="Notas">
          <Textarea
            rows={2}
            value={form.notes}
            onChange={(event) => set('notes', event.target.value)}
          />
        </Field>

        <div className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2.5">
          <div className="min-w-0">
            <p className="text-sm font-medium">Movimento bancário</p>
            <p className="truncate text-xs text-muted-foreground">
              {instance.acquisition_transaction_id
                ? `Ligado (${instance.acquisition_transaction_id.slice(0, 8)}…)`
                : 'Sem ligação ao extrato.'}
            </p>
          </div>
          <div className="flex shrink-0 gap-1">
            {instance.acquisition_transaction_id ? (
              <Button
                variant="ghost"
                size="sm"
                onClick={() =>
                  update.mutate({ id: instance.id, clear_transaction_link: true })
                }
              >
                Remover
              </Button>
            ) : null}
            <Button variant="outline" size="sm" onClick={() => setPickerOpen(true)}>
              <Link2 />
              Escolher
            </Button>
          </div>
        </div>

        <Button
          loading={update.isPending}
          onClick={() =>
            update.mutate({
              id: instance.id,
              acquisition_cost_eur: money(form.acquisition_cost_eur) ?? '0.00',
              acquisition_date: form.acquisition_date || null,
              acquisition_source: form.acquisition_source || null,
              storage_location_id: form.storage_location_id || null,
              clear_storage_location: !form.storage_location_id,
              build_state: form.build_state || null,
              condition: form.condition || null,
              has_box: form.has_box,
              has_instructions: form.has_instructions,
              missing_parts: form.missing_parts || null,
              notes: form.notes || null,
            })
          }
        >
          Guardar alterações
        </Button>
      </div>

      <TransactionPicker
        open={pickerOpen}
        onOpenChange={setPickerOpen}
        nearDate={form.acquisition_date || null}
        amountEur={money(form.acquisition_cost_eur)}
        onSelect={(transaction: TransactionSuggestion) =>
          update.mutate({ id: instance.id, acquisition_transaction_id: transaction.id })
        }
      />
    </>
  );
}

function PhotoControl({ instance }: { instance: LegoSetInstance }) {
  const setPhoto = useSetInstancePhoto();
  const inputRef = React.useRef<HTMLInputElement>(null);

  return (
    <div className="space-y-2">
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) setPhoto.mutate({ id: instance.id, file });
          event.target.value = '';
        }}
      />
      <Button
        variant="outline"
        size="sm"
        loading={setPhoto.isPending}
        onClick={() => inputRef.current?.click()}
      >
        <ImageIcon />
        {instance.photo_url ? 'Substituir fotografia' : 'Carregar fotografia'}
      </Button>
      <p className="text-xs text-muted-foreground">
        A imagem é validada e guardada no NAS; só é servida por ligação assinada e temporária.
      </p>
    </div>
  );
}

export function CopyDetailSheet({
  instance,
  storageLocations,
  onOpenChange,
}: {
  instance: LegoSetInstance | null;
  storageLocations: StorageLocation[];
  onOpenChange: (open: boolean) => void;
}) {
  const { canWrite } = useSession();
  const [addCopyOpen, setAddCopyOpen] = React.useState(false);
  const [confirmDelete, setConfirmDelete] = React.useState(false);
  const deleteInstance = useDeleteInstance();
  const siblings = useModelInstances(instance?.lego_set_model_id ?? null);

  const model = instance?.set_model ?? null;
  const image = instance?.photo_url ?? model?.image_url ?? null;

  return (
    <>
      <Dialog open={Boolean(instance)} onOpenChange={onOpenChange}>
        <SheetContent width="lg" className="p-0">
          {instance && model ? (
            <div className="flex h-full min-h-0 flex-col">
              <div className="shrink-0 border-b border-border">
                <div className="flex gap-4 p-6 pr-12">
                  <div className="size-24 shrink-0 overflow-hidden rounded-lg border border-border bg-muted">
                    {image ? (
                      <img
                        src={image}
                        alt={model.name}
                        className="size-full object-contain"
                        loading="lazy"
                      />
                    ) : (
                      <div className="flex size-full items-center justify-center text-muted-foreground">
                        <Blocks className="size-6" />
                      </div>
                    )}
                  </div>
                  <div className="min-w-0 flex-1 space-y-1.5">
                    <div className="flex flex-wrap items-center gap-2">
                      {model.set_number ? (
                        <Badge variant="secondary" className="numeric">
                          {model.set_number}
                        </Badge>
                      ) : (
                        <Badge variant="secondary">MOC</Badge>
                      )}
                      {model.is_retired ? <Badge variant="warning">retirado</Badge> : null}
                      {instance.ownership_status !== 'IN_COLLECTION' ? (
                        <Badge variant="muted">
                          {OWNERSHIP_LABELS[instance.ownership_status]}
                        </Badge>
                      ) : null}
                      {!instance.is_complete ? (
                        <Badge variant="destructive">incompleto</Badge>
                      ) : null}
                    </div>
                    <h2 className="truncate text-lg font-semibold leading-tight">{model.name}</h2>
                    <p className="text-sm text-muted-foreground">
                      {[model.theme, model.subtheme].filter(Boolean).join(' › ') || '—'}
                    </p>
                    <div className="flex flex-wrap items-center gap-2 pt-1">
                      <RoiPill instance={instance} />
                      {model.owned_copies_count > 1 ? (
                        <Badge variant="outline">{model.owned_copies_count} cópias</Badge>
                      ) : null}
                    </div>
                  </div>
                </div>
              </div>

              <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
                <Tabs defaultValue="overview">
                  <TabsList>
                    <TabsTrigger value="overview">Resumo</TabsTrigger>
                    {canWrite ? <TabsTrigger value="edit">Editar cópia</TabsTrigger> : null}
                    <TabsTrigger value="copies">Cópias</TabsTrigger>
                  </TabsList>

                  <TabsContent value="overview" className="space-y-5">
                    <div className="rounded-lg border border-border p-4">
                      {canWrite ? (
                        <ValueEditor instance={instance} />
                      ) : (
                        <>
                          <p className="numeric text-2xl font-semibold">
                            {eur(model.current_value_eur)}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            atualizado {relativeDays(model.value_updated_at)}
                          </p>
                        </>
                      )}
                    </div>

                    <dl className="divide-y divide-border">
                      <DetailRow label="Custo de aquisição">
                        <span className="numeric">{eur(instance.acquisition_cost_eur)}</span>
                      </DetailRow>
                      <DetailRow label="Valorização">
                        <span
                          className={cn(
                            'numeric',
                            instance.appreciation_eur &&
                              (Number(instance.appreciation_eur) >= 0
                                ? 'text-success'
                                : 'text-destructive'),
                          )}
                        >
                          {signedEur(instance.appreciation_eur)}
                        </span>
                      </DetailRow>
                      <DetailRow label="ROI não realizado">{percent(instance.roi_pct)}</DetailRow>
                      <DetailRow label="Adquirido em">{date(instance.acquisition_date)}</DetailRow>
                      <DetailRow label="Origem">
                        {instance.acquisition_source
                          ? SOURCE_LABELS[instance.acquisition_source]
                          : '—'}
                      </DetailRow>
                      <DetailRow label="Arrumação">{instance.storage_label ?? '—'}</DetailRow>
                      <DetailRow label="Estado de construção">
                        {instance.build_state ? BUILD_STATE_LABELS[instance.build_state] : '—'}
                      </DetailRow>
                      <DetailRow label="Condição">
                        {instance.condition ? (
                          <Badge variant={CONDITION_VARIANTS[instance.condition]}>
                            {CONDITION_LABELS[instance.condition]}
                          </Badge>
                        ) : (
                          '—'
                        )}
                      </DetailRow>
                      <DetailRow label="Caixa / instruções">
                        {[instance.has_box ? 'caixa' : null, instance.has_instructions ? 'instruções' : null]
                          .filter(Boolean)
                          .join(' + ') || 'nenhuma'}
                      </DetailRow>
                      {instance.missing_parts ? (
                        <DetailRow label="Peças em falta">
                          <span className="text-destructive">{instance.missing_parts}</span>
                        </DetailRow>
                      ) : null}
                      {instance.ownership_status === 'SOLD' ? (
                        <DetailRow label="Venda (fora do ROI)">
                          {eur(instance.sale_price_eur)} · {date(instance.sale_date)}
                        </DetailRow>
                      ) : null}
                      {instance.notes ? (
                        <DetailRow label="Notas">{instance.notes}</DetailRow>
                      ) : null}
                    </dl>

                    <Separator />

                    <div className="space-y-3">
                      <p className="text-sm font-medium">Detalhes do conjunto</p>
                      <dl className="divide-y divide-border">
                        <DetailRow label="Ano">{num(model.release_year)}</DetailRow>
                        <DetailRow label="Retirado">{num(model.retired_year)}</DetailRow>
                        <DetailRow label="Peças">{num(model.piece_count)}</DetailRow>
                        <DetailRow label="Minifiguras">{num(model.minifig_count)}</DetailRow>
                        <DetailRow label="PVP original">{eur(model.rrp_eur)}</DetailRow>
                      </dl>
                      {model.short_description ? (
                        <p className="text-sm text-muted-foreground">{model.short_description}</p>
                      ) : null}
                    </div>

                    {model.set_number ? (
                      <div className="flex flex-wrap gap-2">
                        {externalLinks(model.set_number).map((link) => (
                          <Button key={link.label} asChild variant="outline" size="sm">
                            <a href={link.href} target="_blank" rel="noreferrer noopener">
                              {link.label}
                              <ExternalLink />
                            </a>
                          </Button>
                        ))}
                      </div>
                    ) : null}
                  </TabsContent>

                  {canWrite ? (
                    <TabsContent value="edit" className="space-y-6">
                      <EditCopyForm instance={instance} storageLocations={storageLocations} />
                      <Separator />
                      <OwnershipControls instance={instance} />
                      <Separator />
                      <PhotoControl instance={instance} />
                      <Separator />
                      <Button
                        variant="outline"
                        className="text-destructive"
                        onClick={() => setConfirmDelete(true)}
                      >
                        <Trash2 />
                        Eliminar esta cópia
                      </Button>
                    </TabsContent>
                  ) : null}

                  <TabsContent value="copies" className="space-y-3">
                    {canWrite ? (
                      <Button variant="outline" size="sm" onClick={() => setAddCopyOpen(true)}>
                        <Plus />
                        Adicionar outra cópia
                      </Button>
                    ) : null}
                    <ul className="divide-y divide-border rounded-lg border border-border">
                      {(siblings.data ?? []).map((sibling) => (
                        <li
                          key={sibling.id}
                          className={cn(
                            'flex items-center justify-between gap-3 px-4 py-3 text-sm',
                            sibling.id === instance.id && 'bg-muted/50',
                          )}
                        >
                          <div className="min-w-0">
                            <p className="truncate font-medium">
                              {sibling.storage_label ?? 'Sem local'}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {[
                                sibling.build_state ? BUILD_STATE_LABELS[sibling.build_state] : null,
                                sibling.condition ? CONDITION_LABELS[sibling.condition] : null,
                                date(sibling.acquisition_date),
                              ]
                                .filter(Boolean)
                                .join(' · ')}
                            </p>
                          </div>
                          <div className="flex shrink-0 items-center gap-2">
                            {sibling.ownership_status !== 'IN_COLLECTION' ? (
                              <Badge variant="muted">
                                {OWNERSHIP_LABELS[sibling.ownership_status]}
                              </Badge>
                            ) : null}
                            <span className="numeric font-medium">
                              {eur(sibling.acquisition_cost_eur)}
                            </span>
                          </div>
                        </li>
                      ))}
                    </ul>
                  </TabsContent>
                </Tabs>
              </div>
            </div>
          ) : null}
        </SheetContent>
      </Dialog>

      {instance ? (
        <AddCopyDialog
          open={addCopyOpen}
          onOpenChange={setAddCopyOpen}
          modelId={instance.lego_set_model_id}
          modelName={instance.set_model?.name ?? ''}
          entityId={instance.entity_id}
          storageLocations={storageLocations}
        />
      ) : null}

      <Dialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <DialogContent size="sm">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Boxes className="size-4" />
              Eliminar cópia
            </DialogTitle>
          </DialogHeader>
          <DialogBody className="space-y-3 text-sm text-muted-foreground">
            <p>
              <strong className="text-foreground">Arquivar</strong> mantém o histórico e a
              auditoria — a cópia deixa de contar para os totais.
            </p>
            <p>
              <strong className="text-foreground">Eliminar definitivamente</strong> remove a linha
              da base de dados. Use apenas para enganos.
            </p>
          </DialogBody>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setConfirmDelete(false)}>
              Cancelar
            </Button>
            <Button
              variant="outline"
              loading={deleteInstance.isPending}
              onClick={async () => {
                if (!instance) return;
                await deleteInstance.mutateAsync({ id: instance.id });
                setConfirmDelete(false);
                onOpenChange(false);
              }}
            >
              Arquivar
            </Button>
            <Button
              variant="destructive"
              loading={deleteInstance.isPending}
              onClick={async () => {
                if (!instance) return;
                await deleteInstance.mutateAsync({ id: instance.id, hard: true });
                setConfirmDelete(false);
                onOpenChange(false);
              }}
            >
              Eliminar definitivamente
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
