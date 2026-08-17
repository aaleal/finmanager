import * as React from 'react';
import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  ExternalLink,
  Plus,
  RotateCcw,
  ShieldCheck,
  ShieldX,
  Tags,
  XCircle,
} from 'lucide-react';
import type { FsFilter, ReceiptItem } from '@/lib/types';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Field, Input, Textarea } from '@/components/ui/input';
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Skeleton } from '@/components/ui/feedback';
import { EM_DASH, date, eur, percent } from '@/lib/format';
import { cn } from '@/lib/utils';
import { useSession } from '@/features/auth/session';
import { FS_FILTER_OPTIONS, RECEIPT_STATUS_META } from './constants';
import { WhyPopover } from './why-popover';
import { AddFsItemDialog } from './fs-item-dialog';
import { ProductPicker } from './product-picker';
import { ReceiptLinkPanel } from './link-panel';
import { useConfirmReceiptCategories, useReassignItemProduct } from './catalogue-api';
import { useConfirmReceipt, useReceipt, useReparse, useUpdateItem, useVoidReceipt } from './api';

type EditableField = 'unit_price_pvp_eur' | 'promo_discount_eur' | 'quantity';

const LOW_CONFIDENCE = 0.6;

function isLowConfidence(confidence: string | null): boolean {
  if (confidence === null) return false;
  const value = Number(confidence);
  return Number.isFinite(value) && value < LOW_CONFIDENCE;
}

/** Confidence travels as a 0-1 decimal string; the UI shows it as a percentage. */
function confidencePct(confidence: string | null | undefined): number | null {
  if (confidence === null || confidence === undefined) return null;
  const value = Number(confidence);
  return Number.isFinite(value) ? value * 100 : null;
}

function EditableNumberCell({
  item,
  field,
  editing,
  editValue,
  disabled,
  onEditValueChange,
  onStart,
  onCommit,
  onCancel,
}: {
  item: ReceiptItem;
  field: EditableField;
  editing: boolean;
  editValue: string;
  disabled: boolean;
  onEditValueChange: (value: string) => void;
  onStart: () => void;
  onCommit: () => void;
  onCancel: () => void;
}) {
  if (editing) {
    return (
      <Input
        autoFocus
        className="h-7 w-24"
        inputMode="decimal"
        value={editValue}
        onChange={(event) => onEditValueChange(event.target.value)}
        onBlur={onCommit}
        onKeyDown={(event) => {
          if (event.key === 'Enter') onCommit();
          if (event.key === 'Escape') onCancel();
        }}
      />
    );
  }
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onStart}
      className={cn(
        'numeric rounded px-1.5 py-0.5 text-left hover:bg-muted disabled:cursor-default disabled:hover:bg-transparent',
      )}
    >
      {eur(item[field])}
    </button>
  );
}

function ProductCell({ item, disabled }: { item: ReceiptItem; disabled: boolean }) {
  const reassign = useReassignItemProduct();
  return (
    <div className="flex items-center gap-1.5">
      <div className="max-w-[10rem]">
        <ProductPicker
          value={item.display_name ?? item.description_raw}
          merchantDescription={item.description_raw}
          disabled={disabled}
          onSelect={(product) =>
            reassign.mutate({ itemId: item.id, masterProductId: product.id })
          }
        />
      </div>
      {!item.master_product_id ? (
        <span className="flex shrink-0 items-center gap-1 text-xs font-medium text-warning">
          <AlertTriangle className="size-3.5" />
          por resolver
        </span>
      ) : null}
    </div>
  );
}

function ItemRow({
  item,
  index,
  canEdit,
  canReassignProduct,
  editing,
  editValue,
  onEditValueChange,
  onStart,
  onCommit,
  onCancel,
}: {
  item: ReceiptItem;
  index: number;
  canEdit: boolean;
  canReassignProduct: boolean;
  editing: EditableField | null;
  editValue: string;
  onEditValueChange: (value: string) => void;
  onStart: (field: EditableField) => void;
  onCommit: () => void;
  onCancel: () => void;
}) {
  const low = isLowConfidence(item.confidence);
  return (
    <TableRow>
      <TableCell className="text-muted-foreground">{index}</TableCell>
      <TableCell className="max-w-[12rem]">
        <span className="truncate" title={item.description_raw}>
          {item.display_name ?? item.description_raw}
        </span>
      </TableCell>
      <TableCell>
        <ProductCell item={item} disabled={!canReassignProduct} />
      </TableCell>
      <TableCell>{item.merchant_section ?? EM_DASH}</TableCell>
      <TableCell className="numeric whitespace-nowrap">
        <EditableNumberCell
          item={item}
          field="quantity"
          editing={editing === 'quantity'}
          editValue={editValue}
          disabled={!canEdit}
          onEditValueChange={onEditValueChange}
          onStart={() => onStart('quantity')}
          onCommit={onCommit}
          onCancel={onCancel}
        />
        <span className="ml-1 text-xs text-muted-foreground">{item.unit}</span>
      </TableCell>
      <TableCell>
        <EditableNumberCell
          item={item}
          field="unit_price_pvp_eur"
          editing={editing === 'unit_price_pvp_eur'}
          editValue={editValue}
          disabled={!canEdit}
          onEditValueChange={onEditValueChange}
          onStart={() => onStart('unit_price_pvp_eur')}
          onCommit={onCommit}
          onCancel={onCancel}
        />
      </TableCell>
      <TableCell>
        <EditableNumberCell
          item={item}
          field="promo_discount_eur"
          editing={editing === 'promo_discount_eur'}
          editValue={editValue}
          disabled={!canEdit}
          onEditValueChange={onEditValueChange}
          onStart={() => onStart('promo_discount_eur')}
          onCommit={onCommit}
          onCancel={onCancel}
        />
      </TableCell>
      <TableCell className="numeric">{eur(item.invoice_allocated_discount_eur)}</TableCell>
      <TableCell className="numeric font-medium">{eur(item.paid_price_eur)}</TableCell>
      <TableCell className="numeric">
        {item.price_per_kg_final_eur ? (
          eur(item.price_per_kg_final_eur)
        ) : (
          <span title={item.price_per_kg_unavailable_reason ?? undefined}>{EM_DASH}</span>
        )}
      </TableCell>
      <TableCell>
        <div className="flex items-center gap-1.5">
          <span className="numeric">{percent(confidencePct(item.confidence))}</span>
          {low ? (
            <span className="flex items-center gap-1 text-xs font-medium text-warning">
              <AlertTriangle className="size-3.5" />
              incerto
            </span>
          ) : null}
          <WhyPopover reasons={item.decision_reasons} />
        </div>
      </TableCell>
    </TableRow>
  );
}

export function ReceiptReviewPane({
  receiptId,
  onClose,
}: {
  receiptId: string | null;
  onClose: () => void;
}) {
  const { canWrite } = useSession();
  const receiptQuery = useReceipt(receiptId);
  const confirmReceipt = useConfirmReceipt();
  const confirmCategories = useConfirmReceiptCategories();
  const voidReceipt = useVoidReceipt();
  const reparse = useReparse();
  const updateItem = useUpdateItem();

  const [addFsOpen, setAddFsOpen] = React.useState(false);
  const [voidOpen, setVoidOpen] = React.useState(false);
  const [voidReason, setVoidReason] = React.useState('');
  const [editing, setEditing] = React.useState<{ itemId: string; field: EditableField } | null>(
    null,
  );
  const [editValue, setEditValue] = React.useState('');
  const [drafts, setDrafts] = React.useState<Record<string, Partial<Record<EditableField, string>>>>(
    {},
  );
  const [itemsFsFilter, setItemsFsFilter] = React.useState<FsFilter>('all');

  const receipt = receiptQuery.data ?? null;

  React.useEffect(() => {
    if (!receiptId) {
      setEditing(null);
      setDrafts({});
      setVoidOpen(false);
      setVoidReason('');
      setItemsFsFilter('all');
    }
  }, [receiptId]);

  const locked = receipt?.status === 'CONFIRMED' || receipt?.status === 'VOID';
  const canEditItems = canWrite && !locked;

  const draftNumber = React.useCallback(
    (item: ReceiptItem, field: EditableField): number => {
      const draft = drafts[item.id]?.[field];
      const live = editing?.itemId === item.id && editing.field === field ? editValue : undefined;
      const raw = live ?? draft ?? item[field];
      const parsed = Number(String(raw).replace(',', '.'));
      return Number.isFinite(parsed) ? parsed : Number(item[field]);
    },
    [drafts, editing, editValue],
  );

  const isEditingSomething = editing !== null || Object.keys(drafts).length > 0;

  const liveTotal = React.useMemo(() => {
    if (!receipt || !isEditingSomething) return null;
    // `unit_price_pvp_eur` is the *line* gross, so it is never multiplied by the
    // quantity here — only `pvp - promo - alocado` reconciles. An Fs row pays 0,00.
    return receipt.items.reduce((sum, item) => {
      if (item.is_fs) return sum;
      const pvp = draftNumber(item, 'unit_price_pvp_eur');
      const promo = draftNumber(item, 'promo_discount_eur');
      return sum + pvp - promo - Number(item.invoice_allocated_discount_eur);
    }, 0);
  }, [receipt, draftNumber, isEditingSomething]);

  function startEdit(item: ReceiptItem, field: EditableField) {
    if (!canEditItems) return;
    setEditing({ itemId: item.id, field });
    setEditValue(String(item[field]));
  }

  function cancelEdit() {
    setEditing(null);
  }

  async function commitEdit(item: ReceiptItem) {
    if (!editing || !receipt) return;
    const { field } = editing;
    const numeric = Number(editValue.replace(',', '.'));
    setEditing(null);
    if (!Number.isFinite(numeric)) return;
    setDrafts((previous) => ({
      ...previous,
      [item.id]: { ...previous[item.id], [field]: editValue },
    }));
    try {
      await updateItem.mutateAsync({ receiptId: receipt.id, itemId: item.id, patch: { [field]: numeric } });
    } finally {
      setDrafts((previous) => {
        const next = { ...previous };
        delete next[item.id];
        return next;
      });
    }
  }

  // Signed and time-limited: an <iframe> cannot send a CSRF header, so the
  // signature in this URL *is* the authorisation (ADR-0004).
  const documentUrl = receipt?.document_url ?? null;
  const printedItems = receipt?.items.filter((item) => !item.is_fs) ?? [];
  const fsItems = receipt?.items.filter((item) => item.is_fs) ?? [];
  // "Só Fs"/"Sem Fs" hide one of the two tables outright; filtering never refetches.
  const visiblePrintedItems = itemsFsFilter === 'only' ? [] : printedItems;
  const visibleFsItems = itemsFsFilter === 'exclude' ? [] : fsItems;

  return (
    <>
      <Dialog open={Boolean(receiptId)} onOpenChange={(open) => !open && onClose()}>
        <SheetContent width="lg" className="max-w-full p-0 sm:max-w-5xl">
          {receiptQuery.isLoading || !receipt ? (
            <div className="space-y-3 p-6">
              <Skeleton className="h-8" />
              <Skeleton className="h-64" />
            </div>
          ) : (
            <div className="grid h-full min-h-0 grid-cols-1 lg:grid-cols-2">
              <div className="flex min-h-0 flex-col border-b border-border bg-muted lg:border-b-0 lg:border-r">
                <div className="flex shrink-0 items-center justify-between gap-2 border-b border-border bg-card px-4 py-2">
                  <p className="text-sm font-medium">Documento original</p>
                  {documentUrl ? (
                    <a
                      href={documentUrl}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="flex items-center gap-1 text-xs text-primary hover:underline"
                    >
                      Abrir original
                      <ExternalLink className="size-3.5" />
                    </a>
                  ) : null}
                </div>
                <div className="min-h-[16rem] flex-1">
                  {documentUrl ? (
                    <iframe title="Documento original" src={documentUrl} className="size-full border-0" />
                  ) : (
                    <div className="flex size-full items-center justify-center text-sm text-muted-foreground">
                      Sem documento associado.
                    </div>
                  )}
                </div>
              </div>

              <div className="flex min-h-0 flex-col overflow-y-auto px-6 py-5 pr-12">
                <div className="space-y-2 border-b border-border pb-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="text-lg font-semibold leading-tight">
                      {receipt.merchant_name ?? 'Comerciante desconhecido'}
                    </h2>
                    {(() => {
                      const meta = RECEIPT_STATUS_META[receipt.status as keyof typeof RECEIPT_STATUS_META];
                      const Icon = meta?.icon ?? CheckCircle2;
                      return (
                        <Badge variant={meta?.variant ?? 'muted'}>
                          <Icon />
                          {meta?.label ?? receipt.status}
                        </Badge>
                      );
                    })()}
                  </div>
                  <p className="text-sm text-muted-foreground">{date(receipt.purchase_date)}</p>
                  <div className="flex flex-wrap items-center gap-3 text-sm">
                    <span className="flex items-center gap-1.5">
                      ATCUD: {receipt.atcud_code ?? EM_DASH}
                      {receipt.atcud_code ? (
                        receipt.atcud_valid ? (
                          <Badge variant="success">
                            <ShieldCheck />
                            válido
                          </Badge>
                        ) : (
                          <Badge variant="destructive">
                            <ShieldX />
                            inválido
                          </Badge>
                        )
                      ) : null}
                    </span>
                    <span className="flex items-center gap-1.5">
                      Confiança: {percent(confidencePct(receipt.confidence))}
                      <WhyPopover reasons={receipt.decision_reasons} />
                    </span>
                    {receipt.parser_profile_name ? (
                      <Badge variant="outline">{receipt.parser_profile_name}</Badge>
                    ) : null}
                  </div>
                </div>

                <div className="space-y-2 border-b border-border py-4">
                  <div className="flex items-baseline justify-between text-sm">
                    <span className="text-muted-foreground">Total impresso</span>
                    <span className="numeric font-medium">{eur(receipt.total_eur)}</span>
                  </div>
                  <div className="flex items-baseline justify-between text-sm">
                    <span className="text-muted-foreground">Soma das linhas</span>
                    <span className="numeric font-medium">
                      {liveTotal !== null ? eur(liveTotal) : eur(receipt.derived.computed_total_eur)}
                    </span>
                  </div>
                  {receipt.derived.is_reconciled === false ? (
                    <div className="flex items-center gap-2 rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-sm font-medium text-warning">
                      <AlertTriangle className="size-4 shrink-0" />
                      <span>As linhas não batem certo com o total impresso</span>
                      <span className="numeric ml-auto">
                        {eur(receipt.derived.reconciliation_delta_eur)}
                      </span>
                    </div>
                  ) : null}
                  {receipt.derived.fs_item_count > 0 ? (
                    <div className="grid grid-cols-2 gap-x-4 gap-y-1 pt-1 text-xs text-muted-foreground sm:grid-cols-4">
                      <span>Total nocional: {eur(receipt.derived.notional_total_eur)}</span>
                      <span>Valor Fs: {eur(receipt.derived.fs_value_eur)}</span>
                      <span>Artigos Fs: {receipt.derived.fs_item_count}</span>
                      <span>Peso Fs: {percent(receipt.derived.fs_share_pct)}</span>
                    </div>
                  ) : null}
                </div>

                <div className="flex items-center justify-end gap-2 pt-4">
                  <span className="text-xs font-medium text-muted-foreground">Artigos</span>
                  <Select
                    value={itemsFsFilter}
                    onValueChange={(value) => setItemsFsFilter(value as FsFilter)}
                  >
                    <SelectTrigger className="w-32">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {FS_FILTER_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-4 pb-4">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>#</TableHead>
                        <TableHead>Descrição</TableHead>
                        <TableHead>Produto</TableHead>
                        <TableHead>Secção</TableHead>
                        <TableHead>Qtd</TableHead>
                        <TableHead>PVP</TableHead>
                        <TableHead>Promo</TableHead>
                        <TableHead>Desconto fatura</TableHead>
                        <TableHead>Pago</TableHead>
                        <TableHead>€/kg</TableHead>
                        <TableHead>Confiança</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {visiblePrintedItems.map((item, index) => (
                        <ItemRow
                          key={item.id}
                          item={item}
                          index={index + 1}
                          canEdit={canEditItems}
                          canReassignProduct={canWrite}
                          editing={editing?.itemId === item.id ? editing.field : null}
                          editValue={editValue}
                          onEditValueChange={setEditValue}
                          onStart={(field) => startEdit(item, field)}
                          onCommit={() => commitEdit(item)}
                          onCancel={cancelEdit}
                        />
                      ))}
                    </TableBody>
                  </Table>

                  {visibleFsItems.length ? (
                    <div className="space-y-2 rounded-lg border border-dashed border-border p-3">
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-semibold">Artigos Fs</p>
                        <p className="numeric text-sm font-medium">
                          {eur(receipt.derived.fs_value_eur)}
                        </p>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        Nunca estiveram na fatura: o pago é sempre 0,00 e o valor nocional é o
                        PVP vezes a quantidade. Nenhum total impresso muda por causa deles.
                      </p>
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>#</TableHead>
                            <TableHead>Descrição</TableHead>
                            <TableHead>Produto</TableHead>
                            <TableHead>Secção</TableHead>
                            <TableHead>Qtd</TableHead>
                            <TableHead>PVP</TableHead>
                            <TableHead>Promo</TableHead>
                            <TableHead>Desconto fatura</TableHead>
                            <TableHead>Pago</TableHead>
                            <TableHead>€/kg</TableHead>
                            <TableHead>Confiança</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {visibleFsItems.map((item, index) => (
                            <ItemRow
                              key={item.id}
                              item={item}
                              index={index + 1}
                              canEdit={canEditItems}
                              canReassignProduct={canWrite}
                              editing={editing?.itemId === item.id ? editing.field : null}
                              editValue={editValue}
                              onEditValueChange={setEditValue}
                              onStart={(field) => startEdit(item, field)}
                              onCommit={() => commitEdit(item)}
                              onCancel={cancelEdit}
                            />
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  ) : null}
                </div>

                {canWrite ? (
                  <div className="flex flex-wrap items-center gap-2 border-t border-border pt-4">
                    <Button variant="outline" onClick={() => setAddFsOpen(true)}>
                      <Plus />
                      Adicionar artigo Fs
                    </Button>
                    <Button
                      disabled={locked}
                      loading={confirmReceipt.isPending}
                      onClick={() => confirmReceipt.mutate(receipt.id)}
                    >
                      <CheckCircle2 />
                      Confirmar
                    </Button>
                    <Button
                      variant="outline"
                      title="Promove todas as categorias sugeridas desta fatura a confirmadas."
                      loading={confirmCategories.isPending}
                      onClick={() => confirmCategories.mutate(receipt.id)}
                    >
                      <Tags />
                      Confirmar categorias
                    </Button>
                    <Button
                      variant="outline"
                      disabled={receipt.status === 'VOID'}
                      onClick={() => setVoidOpen(true)}
                    >
                      <Ban />
                      Anular
                    </Button>
                    <Button
                      variant="outline"
                      loading={reparse.isPending}
                      onClick={() => reparse.mutate({ receiptId: receipt.id })}
                    >
                      <RotateCcw />
                      Reprocessar
                    </Button>
                  </div>
                ) : null}

                <div className="border-t border-border pt-4">
                  <ReceiptLinkPanel
                    receiptId={receipt.id}
                    purchaseDate={receipt.purchase_date}
                    totalEur={receipt.total_eur}
                  />
                </div>
              </div>
            </div>
          )}
        </SheetContent>
      </Dialog>

      {receipt ? (
        <AddFsItemDialog receiptId={receipt.id} open={addFsOpen} onOpenChange={setAddFsOpen} />
      ) : null}

      <Dialog open={voidOpen} onOpenChange={setVoidOpen}>
        <DialogContent size="sm">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <XCircle className="size-4" />
              Anular fatura
            </DialogTitle>
          </DialogHeader>
          <DialogBody className="space-y-3">
            <p className="text-sm text-muted-foreground">
              A anulação exige um motivo — fica registado com a fatura.
            </p>
            <Field label="Motivo">
              <Textarea
                rows={3}
                value={voidReason}
                onChange={(event) => setVoidReason(event.target.value)}
              />
            </Field>
          </DialogBody>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setVoidOpen(false)}>
              Cancelar
            </Button>
            <Button
              variant="destructive"
              disabled={!voidReason.trim()}
              loading={voidReceipt.isPending}
              onClick={async () => {
                if (!receipt) return;
                await voidReceipt.mutateAsync({ receiptId: receipt.id, reason: voidReason.trim() });
                setVoidOpen(false);
                setVoidReason('');
              }}
            >
              Anular
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
