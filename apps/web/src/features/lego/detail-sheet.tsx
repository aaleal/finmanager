import * as React from 'react';
import {
  AlertTriangle,
  Boxes,
  ExternalLink,
  Image as ImageIcon,
  Link2,
  PencilLine,
  Plus,
  Star,
  Trash2,
} from 'lucide-react';
import type { LegoSetInstance, LegoSetModel, StorageLocation, TransactionSuggestion } from '@/lib/types';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Field, Input, Textarea } from '@/components/ui/input';
import {
  Checkbox,
  Separator,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/primitives';
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
  useDeleteModel,
  useModelInstances,
  useSetGallery,
  useSetInstancePhoto,
  useSetModelImage,
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
import { AddSetDialog } from './add-set-dialog';
import { SetCarousel, frames } from './set-carousel';

function money(value: string) {
  const normalized = value.trim().replace(',', '.');
  if (!normalized) return null;
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed.toFixed(2) : null;
}

function count(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = Number(trimmed);
  return Number.isInteger(parsed) && parsed >= 0 ? parsed : null;
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
            <Input
              type="date"
              value={saleDate}
              onChange={(event) => setSaleDate(event.target.value)}
            />
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

/**
 * Every catalog field of the set, editable in place.
 *
 * The create dialog is not the only place a set can be described: metadata arrives
 * late (a lookup that failed, a PVP found afterwards, a retirement date announced
 * next year), so the sheet edits the same fields rather than sending the user back
 * through "delete and re-add" (M9.2 FR-9.23).
 */
function EditSetForm({ instance }: { instance: LegoSetInstance }) {
  const model = instance.set_model;
  const update = useUpdateModel();
  const setImage = useSetModelImage();
  const fileRef = React.useRef<HTMLInputElement>(null);
  const [form, setForm] = React.useState({
    set_number: model?.set_number ?? '',
    name: model?.name ?? '',
    theme: model?.theme ?? '',
    subtheme: model?.subtheme ?? '',
    release_date: toDateInput(model?.release_date),
    retirement_date: toDateInput(model?.retirement_date),
    piece_count: model?.piece_count?.toString() ?? '',
    minifig_count: model?.minifig_count?.toString() ?? '',
    rrp_eur: model?.rrp_eur ?? '',
    current_value_eur: model?.current_value_eur ?? '',
    short_description: model?.short_description ?? '',
    notes: model?.notes ?? '',
  });

  if (!model) return null;

  function set<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((previous) => ({ ...previous, [key]: value }));
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field
          label="Número do conjunto"
          hint={model.is_custom ? 'Um MOC não tem número.' : undefined}
        >
          <Input
            disabled={model.is_custom}
            value={form.set_number}
            onChange={(event) => set('set_number', event.target.value)}
          />
        </Field>
        <Field label="Nome">
          <Input value={form.name} onChange={(event) => set('name', event.target.value)} />
        </Field>
        <Field label="Tema">
          <Input value={form.theme} onChange={(event) => set('theme', event.target.value)} />
        </Field>
        <Field label="Subtema">
          <Input value={form.subtheme} onChange={(event) => set('subtheme', event.target.value)} />
        </Field>
        <Field label="Data de lançamento">
          <Input
            type="date"
            value={form.release_date}
            onChange={(event) => set('release_date', event.target.value)}
          />
        </Field>
        <Field
          label="Data de retirada"
          hint="Vazio se ainda está à venda. Só conta como retirado depois de a data passar."
        >
          <Input
            type="date"
            value={form.retirement_date}
            onChange={(event) => set('retirement_date', event.target.value)}
          />
        </Field>
        <Field label="Peças">
          <Input
            type="number"
            value={form.piece_count}
            onChange={(event) => set('piece_count', event.target.value)}
          />
        </Field>
        <Field label="Minifiguras">
          <Input
            type="number"
            value={form.minifig_count}
            onChange={(event) => set('minifig_count', event.target.value)}
          />
        </Field>
        <Field label="PVP original (€)">
          <Input
            inputMode="decimal"
            value={form.rrp_eur}
            onChange={(event) => set('rrp_eur', event.target.value)}
          />
        </Field>
        <Field label="Valor de mercado (€)" hint="Alterá-lo volta a marcar a data de atualização.">
          <Input
            inputMode="decimal"
            value={form.current_value_eur}
            onChange={(event) => set('current_value_eur', event.target.value)}
          />
        </Field>
      </div>

      <Field label="Descrição">
        <Textarea
          rows={2}
          value={form.short_description}
          onChange={(event) => set('short_description', event.target.value)}
        />
      </Field>

      <Field label="Notas do conjunto">
        <Textarea
          rows={2}
          value={form.notes}
          onChange={(event) => set('notes', event.target.value)}
        />
      </Field>

      <div className="flex flex-wrap items-center gap-2">
        <Button
          loading={update.isPending}
          onClick={() =>
            update.mutate({
              id: model.id,
              set_number: model.is_custom ? null : form.set_number.trim().toUpperCase() || null,
              name: form.name.trim(),
              theme: form.theme || null,
              subtheme: form.subtheme || null,
              release_date: form.release_date || null,
              retirement_date: form.retirement_date || null,
              piece_count: count(form.piece_count),
              minifig_count: count(form.minifig_count),
              rrp_eur: money(form.rrp_eur),
              current_value_eur: money(form.current_value_eur),
              short_description: form.short_description || null,
              notes: form.notes || null,
            })
          }
        >
          Guardar conjunto
        </Button>
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) setImage.mutate({ id: model.id, file });
            event.target.value = '';
          }}
        />
        <Button
          variant="outline"
          loading={setImage.isPending}
          onClick={() => fileRef.current?.click()}
        >
          <ImageIcon />
          {model.image_url ? 'Substituir imagem' : 'Carregar imagem'}
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">
        Estes campos descrevem o conjunto e valem para todas as cópias.
      </p>

      <Separator />
      <GalleryEditor model={model} />
    </div>
  );
}

/** The carousel's contents: the box shot plus every extra view, reorderable by promotion. */
function GalleryEditor({ model }: { model: LegoSetModel }) {
  const gallery = useSetGallery();
  const fileRef = React.useRef<HTMLInputElement>(null);
  const [url, setUrl] = React.useState('');

  return (
    <div className="space-y-3">
      <div>
        <p className="text-sm font-medium">Galeria do conjunto</p>
        <p className="text-xs text-muted-foreground">
          A caixa é a imagem principal. As restantes servem para inspecionar o conjunto de perto.
        </p>
      </div>

      <ul className="grid grid-cols-3 gap-2 sm:grid-cols-4">
        <li className="space-y-1">
          <div className="aspect-square overflow-hidden rounded border-2 border-primary bg-muted">
            {model.image_url ? (
              <img src={model.image_url} alt="" className="size-full object-cover" loading="lazy" />
            ) : null}
          </div>
          <p className="text-center text-xs font-medium">Principal</p>
        </li>

        {model.images.map((image) => (
          <li key={image.id} className="space-y-1">
            <div className="aspect-square overflow-hidden rounded border border-border bg-muted">
              {image.url ? (
                <img src={image.url} alt="" className="size-full object-cover" loading="lazy" />
              ) : null}
            </div>
            <div className="flex justify-center gap-1">
              <Button
                variant="ghost"
                size="icon-sm"
                title="Tornar principal"
                onClick={() => gallery.promote.mutate({ id: model.id, imageId: image.id })}
              >
                <Star className="size-3.5" />
              </Button>
              <Button
                variant="ghost"
                size="icon-sm"
                title="Remover da galeria"
                className="text-destructive"
                onClick={() => gallery.remove.mutate({ id: model.id, imageId: image.id })}
              >
                <Trash2 className="size-3.5" />
              </Button>
            </div>
          </li>
        ))}
      </ul>

      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) gallery.add.mutate({ id: model.id, file });
          event.target.value = '';
        }}
      />
      <div className="flex flex-wrap items-end gap-2">
        <Field label="Endereço de uma imagem" className="min-w-[12rem] flex-1">
          <Input
            placeholder="https://…"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
          />
        </Field>
        <Button
          variant="outline"
          loading={gallery.add.isPending}
          disabled={!url.trim()}
          onClick={async () => {
            await gallery.add.mutateAsync({ id: model.id, url: url.trim() });
            setUrl('');
          }}
        >
          Adicionar
        </Button>
        <Button variant="outline" onClick={() => fileRef.current?.click()}>
          <ImageIcon />
          Carregar ficheiro
        </Button>
      </div>
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
                onClick={() => update.mutate({ id: instance.id, clear_transaction_link: true })}
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

/**
 * Which of the model's copies is being edited.
 *
 * Reaching the sheet from the grouped view always lands on the first copy, so
 * without this the second copy of a set is unreachable (M9.1).
 */
function CopySwitcher({
  copies,
  current,
  onSelect,
}: {
  copies: LegoSetInstance[];
  current: LegoSetInstance;
  onSelect: (instance: LegoSetInstance) => void;
}) {
  if (copies.length <= 1) return null;

  function label(copy: LegoSetInstance, index: number) {
    return [
      `Cópia ${index + 1}`,
      copy.storage_label,
      copy.acquisition_date ? date(copy.acquisition_date) : null,
    ]
      .filter(Boolean)
      .join(' · ');
  }

  return (
    <Field label="Cópia a editar" hint={`Este conjunto tem ${copies.length} cópias.`}>
      <Select
        value={current.id}
        onValueChange={(id) => {
          const next = copies.find((copy) => copy.id === id);
          if (next) onSelect(next);
        }}
      >
        <SelectTrigger>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {copies.map((copy, index) => (
            <SelectItem key={copy.id} value={copy.id}>
              {label(copy, index)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </Field>
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
  onSelectInstance,
}: {
  instance: LegoSetInstance | null;
  storageLocations: StorageLocation[];
  onOpenChange: (open: boolean) => void;
  onSelectInstance: (instance: LegoSetInstance) => void;
}) {
  const { canWrite } = useSession();
  const [addCopyOpen, setAddCopyOpen] = React.useState(false);
  const [confirmDelete, setConfirmDelete] = React.useState(false);
  const [alsoDeleteModel, setAlsoDeleteModel] = React.useState(false);
  const deleteInstance = useDeleteInstance();
  const deleteModel = useDeleteModel();
  const siblings = useModelInstances(instance?.lego_set_model_id ?? null);
  const copies = siblings.data ?? [];

  const model = instance?.set_model ?? null;
  const gallery = React.useMemo(
    () => frames(model, instance?.photo_url),
    [model, instance?.photo_url],
  );
  const isLastCopy = copies.length <= 1;

  return (
    <>
      <Dialog open={Boolean(instance)} onOpenChange={onOpenChange}>
        <SheetContent width="lg" className="p-0">
          {instance && model ? (
            <div className="flex h-full min-h-0 flex-col">
              <div className="shrink-0 border-b border-border">
                <div className="flex gap-4 p-6 pr-12">
                  <SetCarousel items={gallery} className="w-44 shrink-0" />
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
                        <Badge variant="muted">{OWNERSHIP_LABELS[instance.ownership_status]}</Badge>
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
                    {canWrite ? <TabsTrigger value="set">Editar conjunto</TabsTrigger> : null}
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
                        {[
                          instance.has_box ? 'caixa' : null,
                          instance.has_instructions ? 'instruções' : null,
                        ]
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
                        <DetailRow label="Lançamento">{date(model.release_date)}</DetailRow>
                        <DetailRow label="Retirada">
                          {model.retirement_date ? (
                            <span className={model.is_retired ? '' : 'text-muted-foreground'}>
                              {date(model.retirement_date)}
                              {model.is_retired ? '' : ' (ainda à venda)'}
                            </span>
                          ) : (
                            '—'
                          )}
                        </DetailRow>
                        <DetailRow label="Peças">{num(model.piece_count)}</DetailRow>
                        <DetailRow label="Minifiguras">{num(model.minifig_count)}</DetailRow>
                        <DetailRow label="PVP original">{eur(model.rrp_eur)}</DetailRow>
                        <DetailRow label="Valorização vs PVP">
                          <span
                            className={cn(
                              'numeric',
                              model.rrp_appreciation_eur &&
                                (Number(model.rrp_appreciation_eur) >= 0
                                  ? 'text-success'
                                  : 'text-destructive'),
                            )}
                          >
                            {signedEur(model.rrp_appreciation_eur)}
                          </span>
                        </DetailRow>
                        <DetailRow label="ROI vs PVP">{percent(model.rrp_roi_pct)}</DetailRow>
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
                      <CopySwitcher
                        copies={copies}
                        current={instance}
                        onSelect={onSelectInstance}
                      />
                      <EditCopyForm instance={instance} storageLocations={storageLocations} />
                      <Separator />
                      <OwnershipControls instance={instance} />
                      <Separator />
                      <PhotoControl instance={instance} />
                      <Separator />
                      <Button
                        variant="outline"
                        className="text-destructive"
                        onClick={() => {
                          setAlsoDeleteModel(false);
                          setConfirmDelete(true);
                        }}
                      >
                        <Trash2 />
                        Eliminar esta cópia
                      </Button>
                    </TabsContent>
                  ) : null}

                  {canWrite ? (
                    <TabsContent value="set">
                      <EditSetForm instance={instance} />
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
                      {copies.map((sibling) => (
                        <li key={sibling.id}>
                          <button
                            type="button"
                            onClick={() => onSelectInstance(sibling)}
                            className={cn(
                              'flex w-full items-center justify-between gap-3 px-4 py-3 text-left text-sm transition-colors hover:bg-muted/60',
                              sibling.id === instance.id && 'bg-muted/50',
                            )}
                          >
                            <div className="min-w-0">
                              <p className="truncate font-medium">
                                {sibling.storage_label ?? 'Sem local'}
                                {sibling.id === instance.id ? (
                                  <span className="ml-2 text-xs font-normal text-muted-foreground">
                                    (em edição)
                                  </span>
                                ) : null}
                              </p>
                              <p className="text-xs text-muted-foreground">
                                {[
                                  sibling.build_state
                                    ? BUILD_STATE_LABELS[sibling.build_state]
                                    : null,
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
                          </button>
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
        <AddSetDialog
          open={addCopyOpen}
          onOpenChange={setAddCopyOpen}
          storageLocations={storageLocations}
          existingModel={{
            id: instance.lego_set_model_id,
            name: instance.set_model?.name ?? '',
            setNumber: instance.set_model?.set_number ?? null,
            entityId: instance.entity_id,
          }}
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
              <strong className="text-foreground">Arquivar</strong> mantém o histórico e a auditoria
              — a cópia deixa de contar para os totais.
            </p>
            <p>
              <strong className="text-foreground">Eliminar definitivamente</strong> remove a linha
              da base de dados. Use apenas para enganos.
            </p>
            {isLastCopy ? (
              <label className="flex cursor-pointer items-start gap-2 rounded-lg border border-border p-3 text-foreground">
                <Checkbox
                  className="mt-0.5"
                  checked={alsoDeleteModel}
                  onCheckedChange={(checked) => setAlsoDeleteModel(checked === true)}
                />
                <span>
                  Eliminar também o conjunto do catálogo
                  <span className="block text-xs text-muted-foreground">
                    Esta é a última cópia. Sem isto, o conjunto fica no catálogo sem cópias.
                  </span>
                </span>
              </label>
            ) : null}
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
                if (alsoDeleteModel) {
                  await deleteModel.mutateAsync({ id: instance.lego_set_model_id });
                }
                setConfirmDelete(false);
                onOpenChange(false);
              }}
            >
              Arquivar
            </Button>
            <Button
              variant="destructive"
              loading={deleteInstance.isPending || deleteModel.isPending}
              onClick={async () => {
                if (!instance) return;
                await deleteInstance.mutateAsync({ id: instance.id, hard: true });
                if (alsoDeleteModel) {
                  await deleteModel.mutateAsync({ id: instance.lego_set_model_id, hard: true });
                }
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
