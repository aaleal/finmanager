import * as React from 'react';
import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  ExternalLink,
  Maximize2,
  Plus,
  RotateCcw,
  ShieldCheck,
  ShieldX,
  Tags,
  XCircle,
  ZoomIn,
  ZoomOut,
} from 'lucide-react';
import type { ProductSearchResult, ReceiptItem } from '@/lib/types';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Field, Input, Textarea } from '@/components/ui/input';
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  FullscreenContent,
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
import { EM_DASH, date, eur, packLabel, percent, quantity, weightKg } from '@/lib/format';
import { cn } from '@/lib/utils';
import { useSession } from '@/features/auth/session';
import { RECEIPT_STATUS_META } from './constants';
import { WhyPopover } from './why-popover';
import { AddFsItemDialog } from './fs-item-dialog';
import { ProductPicker } from './product-picker';
import { ProductCreateDialog } from './product-create-dialog';
import { ReceiptLinkPanel } from './link-panel';
import {
  useAddPackVariant,
  useConfirmReceiptCategories,
  useReassignItemProduct,
} from './catalogue-api';
import {
  useConfirmReceipt,
  useReceipt,
  useReparse,
  useUpdateItem,
  useUpdateReceipt,
  useVoidReceipt,
} from './api';

type EditableField = 'unit_price_pvp_eur' | 'promo_discount_eur' | 'quantity' | 'weight_listed_kg';

const LOW_CONFIDENCE = 0.6;
const ZOOM_STEPS = [0.6, 0.75, 1, 1.25, 1.5, 2, 3];

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
      {/* A quantity is a count, not money — formatting it as EUR made `1` read
          as `1,00 €`. Weight is the separate column beside it. */}
      {field === 'quantity' ? quantity(item.quantity) : eur(item[field])}
    </button>
  );
}

function ProductCell({
  item,
  disabled,
  onCreateProduct,
}: {
  item: ReceiptItem;
  disabled: boolean;
  onCreateProduct: (item: ReceiptItem, name: string) => void;
}) {
  const reassign = useReassignItemProduct();
  return (
    <div className="flex items-center gap-1.5">
      <div className="min-w-0 flex-1">
        <ProductPicker
          value={item.display_name ?? item.description_raw}
          merchantDescription={item.description_raw}
          disabled={disabled}
          onSelect={(product: ProductSearchResult) =>
            reassign.mutate({ itemId: item.id, masterProductId: product.id })
          }
          onCreate={disabled ? undefined : (name) => onCreateProduct(item, name)}
        />
      </div>
      {!item.master_product_id ? (
        <span
          className="flex shrink-0 items-center gap-1 text-xs font-medium text-warning"
          title="Esta linha ainda não resolveu para um produto — sem produto não há categoria."
        >
          <AlertTriangle className="size-3.5" />
        </span>
      ) : null}
    </div>
  );
}

/**
 * The weight, and whether it is a format the product already knows about.
 *
 * The match is by value at the gram: with unique weights per product there is
 * exactly one format a line can mean, so nothing has to be referenced. What the
 * invoice printed is a **proposal** — the format only joins the catalogue when a
 * human says so, which is what keeps the curated list curated.
 */
function WeightCell({
  item,
  canEdit,
  editing,
  editValue,
  onEditValueChange,
  onStart,
  onCommit,
  onCancel,
}: {
  item: ReceiptItem;
  canEdit: boolean;
  editing: boolean;
  editValue: string;
  onEditValueChange: (value: string) => void;
  onStart: () => void;
  onCommit: () => void;
  onCancel: () => void;
}) {
  const addVariant = useAddPackVariant();
  const productId = item.master_product_id;
  const listed = item.weight_listed_kg;

  // Weighed at the counter: the scale is the answer and there is no format.
  if (item.sold_by_weight) {
    return (
      <span className="numeric" title="Pesado ao balcão — o peso vem da balança.">
        {weightKg(item.weight_kg)}
      </span>
    );
  }

  return (
    <div className="flex items-center gap-1">
      {editing ? (
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
      ) : (
        <button
          type="button"
          disabled={!canEdit}
          onClick={onStart}
          title="Peso da embalagem, em kg."
          className="numeric rounded px-1.5 py-0.5 text-left hover:bg-muted disabled:cursor-default disabled:hover:bg-transparent"
        >
          {weightKg(item.weight_kg)}
        </button>
      )}
      {item.pack_weight_is_known === true ? (
        <CheckCircle2
          className="size-3.5 shrink-0 text-success"
          aria-label={`${packLabel(listed)} é um formato deste produto`}
        />
      ) : null}
      {item.pack_weight_is_known === false && productId && listed ? (
        <Button
          size="icon-sm"
          variant="ghost"
          disabled={!canEdit || addVariant.isPending}
          title={`${packLabel(listed)} ainda não é um formato de ${item.display_name} — adicionar`}
          aria-label={`Adicionar o formato ${packLabel(listed)} a este produto`}
          onClick={() => addVariant.mutate({ productId, weightKg: String(listed) })}
        >
          <Plus className="text-warning" />
        </Button>
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
  onCreateProduct,
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
  onCreateProduct: (item: ReceiptItem, name: string) => void;
}) {
  const low = isLowConfidence(item.confidence);
  return (
    <TableRow>
      <TableCell className="text-muted-foreground">{index}</TableCell>
      <TableCell className="max-w-[14rem]">
        <span className="truncate" title={item.description_raw}>
          {item.display_name ?? item.description_raw}
        </span>
      </TableCell>
      <TableCell className="w-64">
        <ProductCell item={item} disabled={!canReassignProduct} onCreateProduct={onCreateProduct} />
      </TableCell>
      {/* The category lives on the product and nowhere else, so it is shown as
          the full `L1 › L2 › L3` path: the same leaf name under two parents is
          never ambiguous (FR-1.3, Decision #34). */}
      <TableCell className="max-w-[13rem]">
        <span className="block truncate text-xs" title={item.category_path ?? undefined}>
          {item.category_path ?? EM_DASH}
        </span>
      </TableCell>
      <TableCell className="numeric whitespace-nowrap" title={`${item.quantity} ${item.unit}`}>
        {item.sold_by_weight ? (
          EM_DASH
        ) : (
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
        )}
      </TableCell>
      <TableCell className="numeric whitespace-nowrap">
        <WeightCell
          item={item}
          canEdit={canEdit}
          editing={editing === 'weight_listed_kg'}
          editValue={editValue}
          onEditValueChange={onEditValueChange}
          onStart={() => onStart('weight_listed_kg')}
          onCommit={onCommit}
          onCancel={onCancel}
        />
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
      {/* Only the icon: the percentage cost a whole column and said less than
          the reasons behind it. Uncertainty is still flagged by icon and label,
          never by colour alone. */}
      <TableCell>
        <div className="flex items-center gap-1">
          {low ? (
            <AlertTriangle className="size-3.5 shrink-0 text-warning" aria-label="Valor incerto" />
          ) : null}
          <WhyPopover
            reasons={item.decision_reasons}
            label={null}
            title={`Confiança ${percent(confidencePct(item.confidence))} — porquê?`}
          />
        </div>
      </TableCell>
    </TableRow>
  );
}

const ITEM_COLUMNS: { label: string; title?: string }[] = [
  { label: '#' },
  { label: 'Descrição' },
  { label: 'Produto' },
  { label: 'Categoria' },
  { label: 'Qtd' },
  { label: 'Peso' },
  { label: 'PVP' },
  { label: 'Promo' },
  {
    label: 'Desconto fatura',
    title:
      'Repartição automática do desconto da fatura por cada linha. Edite o desconto no cabeçalho — a repartição é refeita a seguir.',
  },
  { label: 'Pago' },
  { label: '€/kg' },
  { label: '?' },
];

function ItemTableHead() {
  return (
    <TableHeader>
      <TableRow>
        {ITEM_COLUMNS.map((column) => (
          <TableHead key={column.label} title={column.title}>
            {column.label}
          </TableHead>
        ))}
      </TableRow>
    </TableHeader>
  );
}

/**
 * A total that is an **input**, edited in place.
 *
 * The invoice discount is one of them: the per-line `Desconto fatura` column is
 * its proration, recomputed on every edit, so it is here that it is changed.
 */
function EditableTotalRow({
  label,
  value,
  hint,
  disabled,
  onSave,
}: {
  label: string;
  value: string | number | null;
  hint?: string;
  disabled: boolean;
  onSave: (value: number) => void;
}) {
  const [draft, setDraft] = React.useState<string | null>(null);

  function commit() {
    const raw = draft ?? '';
    setDraft(null);
    const numeric = Number(raw.trim().replace(',', '.'));
    if (!Number.isFinite(numeric) || numeric === Number(value)) return;
    onSave(numeric);
  }

  return (
    <div className="flex items-baseline justify-between text-sm">
      <span className="text-muted-foreground" title={hint}>
        {label}
      </span>
      {draft === null ? (
        <button
          type="button"
          disabled={disabled}
          onClick={() => setDraft(value === null ? '' : String(value))}
          className="numeric rounded px-1.5 py-0.5 font-medium hover:bg-muted disabled:cursor-default disabled:hover:bg-transparent"
        >
          {eur(value)}
        </button>
      ) : (
        <Input
          autoFocus
          className="h-7 w-28"
          inputMode="decimal"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onBlur={commit}
          onKeyDown={(event) => {
            if (event.key === 'Enter') commit();
            if (event.key === 'Escape') setDraft(null);
          }}
        />
      )}
    </div>
  );
}

/**
 * Fetch the signed document once and hand the frame a `blob:` URL.
 *
 * Framing the signed URL directly is at the mercy of whatever the origin sends
 * back — a global `X-Frame-Options: DENY`, or a stale service worker answering
 * with the SPA shell, both collapse the pane into "recusou-se a ligar". A blob
 * has no response headers and no service worker in front of it.
 */
function useDocumentBlob(url: string | null) {
  const [objectUrl, setObjectUrl] = React.useState<string | null>(null);
  const [failed, setFailed] = React.useState(false);

  React.useEffect(() => {
    if (!url) {
      setObjectUrl(null);
      setFailed(false);
      return;
    }
    let revoked: string | null = null;
    const controller = new AbortController();
    setObjectUrl(null);
    setFailed(false);

    fetch(url, { credentials: 'same-origin', signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(String(response.status));
        return response.blob();
      })
      .then((blob) => {
        revoked = URL.createObjectURL(blob);
        setObjectUrl(revoked);
      })
      .catch((error: unknown) => {
        if ((error as Error)?.name !== 'AbortError') setFailed(true);
      });

    return () => {
      controller.abort();
      if (revoked) URL.revokeObjectURL(revoked);
    };
  }, [url]);

  return { objectUrl, failed };
}

/** The original, narrow but zoomable — reading a thermal *talão* needs both. */
function DocumentPane({ url }: { url: string | null }) {
  const [zoomIndex, setZoomIndex] = React.useState(2);
  const zoom = ZOOM_STEPS[zoomIndex] ?? 1;
  const { objectUrl, failed } = useDocumentBlob(url);

  return (
    <div className="flex min-h-0 flex-col border-b border-border bg-muted lg:border-b-0 lg:border-r">
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-border bg-card px-3 py-2">
        <p className="text-sm font-medium">Documento original</p>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label="Reduzir"
            disabled={zoomIndex === 0}
            onClick={() => setZoomIndex((index) => Math.max(0, index - 1))}
          >
            <ZoomOut />
          </Button>
          <span className="numeric w-12 text-center text-xs text-muted-foreground">
            {Math.round(zoom * 100)} %
          </span>
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label="Ampliar"
            disabled={zoomIndex === ZOOM_STEPS.length - 1}
            onClick={() => setZoomIndex((index) => Math.min(ZOOM_STEPS.length - 1, index + 1))}
          >
            <ZoomIn />
          </Button>
          <Button variant="ghost" size="icon-sm" aria-label="Repor" onClick={() => setZoomIndex(2)}>
            <Maximize2 />
          </Button>
          {objectUrl ? (
            <a
              href={objectUrl}
              target="_blank"
              rel="noreferrer noopener"
              className="ml-1 flex items-center gap-1 text-xs text-primary hover:underline"
            >
              Abrir
              <ExternalLink className="size-3.5" />
            </a>
          ) : null}
        </div>
      </div>
      <div className="min-h-[16rem] flex-1 overflow-auto">
        {!url ? (
          <div className="flex size-full items-center justify-center px-6 text-center text-sm text-muted-foreground">
            Sem documento associado — esta fatura não veio de um carregamento, por isso não há
            original para mostrar nem para reprocessar.
          </div>
        ) : failed ? (
          <div className="flex size-full items-center justify-center px-6 text-center text-sm text-muted-foreground">
            Não foi possível carregar o original. A ligação assinada expira ao fim de alguns minutos
            — feche e reabra a fatura.
          </div>
        ) : !objectUrl ? (
          <div className="p-3">
            <Skeleton className="h-64" />
          </div>
        ) : (
          <div
            style={{
              width: `${100 / zoom}%`,
              height: `${100 / zoom}%`,
              transform: `scale(${zoom})`,
              transformOrigin: 'top left',
            }}
          >
            <iframe title="Documento original" src={objectUrl} className="size-full border-0" />
          </div>
        )}
      </div>
    </div>
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
  const updateReceipt = useUpdateReceipt();
  const reassign = useReassignItemProduct();

  const [addFsOpen, setAddFsOpen] = React.useState(false);
  const [voidOpen, setVoidOpen] = React.useState(false);
  const [voidReason, setVoidReason] = React.useState('');
  const [newProduct, setNewProduct] = React.useState<{ itemId: string; name: string } | null>(null);
  const [editing, setEditing] = React.useState<{ itemId: string; field: EditableField } | null>(
    null,
  );
  const [editValue, setEditValue] = React.useState('');
  const [drafts, setDrafts] = React.useState<
    Record<string, Partial<Record<EditableField, string>>>
  >({});

  const receipt = receiptQuery.data ?? null;

  React.useEffect(() => {
    if (!receiptId) {
      setEditing(null);
      setDrafts({});
      setVoidOpen(false);
      setVoidReason('');
      setNewProduct(null);
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
    setEditValue(item[field] === null ? '' : String(item[field]));
  }

  function cancelEdit() {
    setEditing(null);
  }

  async function commitEdit(item: ReceiptItem) {
    if (!editing || !receipt) return;
    const { field } = editing;
    const raw = editValue.trim();
    setEditing(null);
    // Clearing the pack weight is a real answer: nobody knows the size, and a
    // fabricated one would silently move the €/kg it divides into.
    const cleared = raw === '' && field === 'weight_listed_kg';
    const numeric = Number(raw.replace(',', '.'));
    if (!cleared && !Number.isFinite(numeric)) return;
    setDrafts((previous) => ({
      ...previous,
      [item.id]: { ...previous[item.id], [field]: editValue },
    }));
    try {
      await updateItem.mutateAsync({
        receiptId: receipt.id,
        itemId: item.id,
        patch: { [field]: cleared ? null : numeric },
      });
    } finally {
      setDrafts((previous) => {
        const next = { ...previous };
        delete next[item.id];
        return next;
      });
    }
  }

  const documentUrl = receipt?.document_url ?? null;
  const printedItems = receipt?.items.filter((item) => !item.is_fs) ?? [];
  const fsItems = receipt?.items.filter((item) => item.is_fs) ?? [];

  const itemRowProps = (item: ReceiptItem) => ({
    item,
    canEdit: canEditItems,
    canReassignProduct: canWrite,
    editing: editing?.itemId === item.id ? editing.field : null,
    editValue,
    onEditValueChange: setEditValue,
    onStart: (field: EditableField) => startEdit(item, field),
    onCommit: () => commitEdit(item),
    onCancel: cancelEdit,
    onCreateProduct: (target: ReceiptItem, name: string) =>
      setNewProduct({ itemId: target.id, name }),
  });

  return (
    <>
      <Dialog open={Boolean(receiptId)} onOpenChange={(open) => !open && onClose()}>
        <FullscreenContent>
          {receiptQuery.isLoading || !receipt ? (
            <div className="space-y-3 p-6">
              <Skeleton className="h-8" />
              <Skeleton className="h-64" />
            </div>
          ) : (
            // The crown-jewel flow gets the whole screen: a narrow but zoomable
            // document column beside a wide line-item column (UX-1.2).
            <div className="grid h-full min-h-0 grid-cols-1 lg:grid-cols-[minmax(18rem,26rem)_1fr]">
              <DocumentPane url={documentUrl} />

              <div className="flex min-h-0 flex-col overflow-y-auto px-6 py-5 pr-12">
                <div className="space-y-2 border-b border-border pb-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="text-lg font-semibold leading-tight">
                      {receipt.merchant_name ?? 'Comerciante desconhecido'}
                    </h2>
                    {(() => {
                      const meta =
                        RECEIPT_STATUS_META[receipt.status as keyof typeof RECEIPT_STATUS_META];
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
                    <Badge variant="outline">
                      {receipt.parser_profile_name ?? 'Sem perfil de leitura'}
                    </Badge>
                  </div>
                </div>

                <div className="space-y-2 border-b border-border py-4">
                  <div className="flex items-baseline justify-between text-sm">
                    <span className="text-muted-foreground">Total impresso</span>
                    <span className="numeric font-medium">{eur(receipt.total_eur)}</span>
                  </div>
                  <EditableTotalRow
                    label="Desconto da fatura"
                    hint="Reparte-se por todas as linhas na coluna «Desconto fatura», que por isso não se edita linha a linha."
                    value={receipt.total_discount_eur}
                    disabled={!canEditItems}
                    onSave={(total_discount_eur) =>
                      updateReceipt.mutate({
                        receiptId: receipt.id,
                        patch: { total_discount_eur },
                      })
                    }
                  />
                  <div className="flex items-baseline justify-between text-sm">
                    <span className="text-muted-foreground">Soma das linhas</span>
                    <span className="numeric font-medium">
                      {liveTotal !== null
                        ? eur(liveTotal)
                        : eur(receipt.derived.computed_total_eur)}
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

                <div className="space-y-4 pb-4 pt-4 [&_table]:text-xs [&_td]:py-1 [&_th]:h-7">
                  <Table>
                    <ItemTableHead />
                    <TableBody>
                      {printedItems.map((item, index) => (
                        <ItemRow key={item.id} index={index + 1} {...itemRowProps(item)} />
                      ))}
                    </TableBody>
                  </Table>

                  <div className="space-y-2 rounded-lg border border-dashed border-border p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-sm font-semibold">Artigos Fs</p>
                      <div className="flex items-center gap-3">
                        <p className="numeric text-sm font-medium">
                          {eur(receipt.derived.fs_value_eur)}
                        </p>
                        {canWrite ? (
                          <Button size="sm" variant="outline" onClick={() => setAddFsOpen(true)}>
                            <Plus />
                            Adicionar artigo Fs
                          </Button>
                        ) : null}
                      </div>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Nunca estiveram na fatura: o pago é sempre 0,00 e o valor nocional é o PVP
                      vezes a quantidade.
                    </p>
                    {fsItems.length ? (
                      <Table>
                        <ItemTableHead />
                        <TableBody>
                          {fsItems.map((item, index) => (
                            <ItemRow key={item.id} index={index + 1} {...itemRowProps(item)} />
                          ))}
                        </TableBody>
                      </Table>
                    ) : (
                      <p className="py-2 text-sm text-muted-foreground">
                        Nenhum artigo Fs nesta fatura.
                      </p>
                    )}
                  </div>
                </div>

                {canWrite ? (
                  <div className="flex flex-wrap items-center gap-2 border-t border-border pt-4">
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
                      title="Marca como verificadas as categorias que o sistema sugeriu (AUTO) para os produtos desta fatura. É uma confirmação por produto, não por linha: vale para todas as compras passadas e futuras do mesmo produto."
                      loading={confirmCategories.isPending}
                      onClick={() => confirmCategories.mutate(receipt.id)}
                    >
                      <Tags />
                      Confirmar categorias sugeridas
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
                      title="Reprocessa a partir do documento guardado — nunca pede um novo carregamento."
                      disabled={!receipt.document_id}
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
        </FullscreenContent>
      </Dialog>

      {receipt ? (
        <AddFsItemDialog receiptId={receipt.id} open={addFsOpen} onOpenChange={setAddFsOpen} />
      ) : null}

      {/* Creating a product mid-review resolves the line that prompted it, so the
          reviewer never has to leave the invoice to visit the catalogue. */}
      <ProductCreateDialog
        open={newProduct !== null}
        initialName={newProduct?.name ?? ''}
        onOpenChange={(open) => !open && setNewProduct(null)}
        onCreated={(product) => {
          if (newProduct) {
            reassign.mutate({ itemId: newProduct.itemId, masterProductId: product.id });
          }
          setNewProduct(null);
        }}
      />

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
