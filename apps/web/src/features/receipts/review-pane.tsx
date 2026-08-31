import * as React from 'react';
import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  ExternalLink,
  HelpCircle,
  Maximize2,
  Plus,
  RotateCcw,
  ShieldCheck,
  ShieldX,
  Tags,
  Trash2,
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
import {
  EM_DASH,
  date,
  eur,
  packLabel,
  percent,
  quantity,
  weightCompact,
  weightKg,
} from '@/lib/format';
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
  useDeleteItem,
  useReceipt,
  useReopenReceipt,
  useReparse,
  useUpdateItem,
  useUpdateReceipt,
  useVoidReceipt,
} from './api';

type EditableField =
  | 'unit_price_pvp_eur'
  | 'promo_discount_eur'
  | 'quantity'
  | 'weight_listed_kg'
  | 'line_no';

/** Cleared to `null` rather than to zero: not knowing is a real answer. */
const CLEARABLE_FIELDS: EditableField[] = ['weight_listed_kg', 'line_no'];

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

/** What the line cost before the invoice-level credit was spread over it. Cents,
 * so two decimal strings never subtract into a float artefact. */
function lineTotalEur(item: ReceiptItem): number {
  const cents = (value: string) => Math.round(Number(value) * 100);
  return (cents(item.unit_price_pvp_eur) - cents(item.promo_discount_eur)) / 100;
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
        className={cn('h-7', field === 'line_no' ? 'w-10 px-1' : 'w-24')}
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
        'numeric rounded py-0.5 text-left hover:bg-muted disabled:cursor-default disabled:hover:bg-transparent',
        field === 'line_no' ? 'px-1' : 'px-1.5',
      )}
    >
      {/* A quantity is a count, not money — formatting it as EUR made `1` read
          as `1,00 €`. Weight is the separate column beside it. */}
      {field === 'quantity'
        ? quantity(item.quantity)
        : field === 'line_no'
          ? (item.line_no ?? EM_DASH)
          : eur(item[field])}
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
      <span className="numeric" title={`${weightKg(item.weight_kg)} — pesado ao balcão.`}>
        {weightCompact(item.weight_kg)}
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
          title={`${weightKg(item.weight_kg)} — peso da embalagem.`}
          className="numeric rounded px-1.5 py-0.5 text-left hover:bg-muted disabled:cursor-default disabled:hover:bg-transparent"
        >
          {weightCompact(item.weight_kg)}
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
          title={
            canEdit
              ? `${packLabel(listed)} ainda não é um formato de ${item.display_name} — adicionar`
              : 'Fatura confirmada ou anulada: reabra-a para acrescentar o formato.'
          }
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
  canEdit,
  canReassignProduct,
  editing,
  editValue,
  onEditValueChange,
  onStart,
  onCommit,
  onCancel,
  onCreateProduct,
  onRemove,
}: {
  item: ReceiptItem;
  canEdit: boolean;
  canReassignProduct: boolean;
  editing: EditableField | null;
  editValue: string;
  onEditValueChange: (value: string) => void;
  onStart: (field: EditableField) => void;
  onCommit: () => void;
  onCancel: () => void;
  onCreateProduct: (item: ReceiptItem, name: string) => void;
  onRemove?: () => void;
}) {
  const low = isLowConfidence(item.confidence);
  return (
    <TableRow className="group/row">
      {/* The line number is where the line sits on the paper, so it is editable:
          correcting it is how a hand-added line takes its real place. The remove
          control sits under it, in the height the Artigo cell already occupies. */}
      <TableCell className="w-8 align-top text-muted-foreground">
        <EditableNumberCell
          item={item}
          field="line_no"
          editing={editing === 'line_no'}
          editValue={editValue}
          disabled={!canEdit || item.is_fs}
          onEditValueChange={onEditValueChange}
          onStart={() => onStart('line_no')}
          onCommit={onCommit}
          onCancel={onCancel}
        />
        {onRemove ? (
          <button
            type="button"
            onClick={onRemove}
            title="Remover esta linha"
            aria-label={`Remover ${item.display_name ?? item.description_raw}`}
            className="mt-0.5 hidden size-5 items-center justify-center rounded text-destructive hover:bg-muted focus-visible:flex group-hover/row:flex"
          >
            <Trash2 className="size-3" />
          </button>
        ) : null}
      </TableCell>
      {/* One column, two truths: the product we decided on, and beneath it the
          text the till actually printed — which is the evidence against paper,
          not a second name. Separate columns showed the same string twice. */}
      <TableCell className="w-52 max-w-[13rem]">
        <ProductCell item={item} disabled={!canReassignProduct} onCreateProduct={onCreateProduct} />
        <div className="mt-0.5 flex items-center gap-1">
          <span
            className="min-w-0 flex-1 truncate text-[0.65rem] uppercase tracking-wide text-muted-foreground"
            title={item.description_raw}
          >
            {item.description_raw}
          </span>
          {low ? (
            <span
              className="flex shrink-0 items-center gap-0.5 text-[0.65rem] font-medium text-warning"
              title="Valor incerto — confirme contra o documento."
            >
              <AlertTriangle className="size-3" />
              {percent(confidencePct(item.confidence))}
            </span>
          ) : null}
          {item.decision_reasons.length ? (
            <WhyPopover
              reasons={item.decision_reasons}
              label={null}
              title={`Confiança ${percent(confidencePct(item.confidence))} — porquê?`}
            />
          ) : null}
        </div>
      </TableCell>
      {/* The category lives on the product and nowhere else, so it is shown as
          the full `L1 › L2 › L3` path: the same leaf name under two parents is
          never ambiguous (FR-1.3, Decision #34). */}
      <TableCell className="max-w-[11rem] align-top">
        <span className="line-clamp-2 text-xs" title={item.category_path ?? undefined}>
          {item.category_path ?? EM_DASH}
        </span>
        {/* Which lines the «Confirmar categorias» button would settle. */}
        {item.category_status === 'AUTO' ? (
          <span
            className="mt-0.5 flex items-center gap-0.5 text-[0.65rem] text-warning"
            title="Categoria sugerida por uma máquina, ainda por confirmar."
          >
            <HelpCircle className="size-3" />
            sugerida
          </span>
        ) : null}
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
      {/* The line's own promotion is an input; the invoice's share is the
          proration of a figure edited in the header. Both are discounts, so they
          share a column instead of costing two. */}
      <TableCell className="whitespace-nowrap">
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
        {Number(item.invoice_allocated_discount_eur) !== 0 ? (
          <div
            className="numeric px-1.5 text-[0.65rem] text-muted-foreground"
            title="Parte do desconto global da fatura atribuída a esta linha."
          >
            {eur(item.invoice_allocated_discount_eur)}
          </div>
        ) : null}
      </TableCell>
      <TableCell className="numeric whitespace-nowrap font-medium">
        {eur(lineTotalEur(item))}
        {Number(item.invoice_allocated_discount_eur) !== 0 ? (
          <div
            className="text-[0.65rem] font-normal text-muted-foreground"
            title="Já com a fatia do desconto global da fatura — é este o valor que entra no histórico de preços."
          >
            {eur(item.paid_price_eur)}
          </div>
        ) : null}
      </TableCell>
      <TableCell className="numeric">
        {item.price_per_kg_final_eur ? (
          <>
            <span title="Sobre o preço efetivamente pago.">
              {eur(item.price_per_kg_final_eur)}
            </span>
            {/* The shelf reading, and only when the two differ. */}
            {item.price_per_kg_pvp_eur &&
            item.price_per_kg_pvp_eur !== item.price_per_kg_final_eur ? (
              <div
                className="text-[0.65rem] font-normal text-muted-foreground"
                title="Sobre o PVP, sem promoção nem desconto da fatura."
              >
                {eur(item.price_per_kg_pvp_eur)}
              </div>
            ) : null}
          </>
        ) : (
          <span title={item.price_per_kg_unavailable_reason ?? undefined}>{EM_DASH}</span>
        )}
      </TableCell>
    </TableRow>
  );
}

const ITEM_COLUMNS: { label: string; title?: string }[] = [
  { label: '#' },
  { label: 'Artigo', title: 'O produto a que a linha resolveu, e por baixo o texto impresso.' },
  { label: 'Categoria' },
  { label: 'Qtd' },
  { label: 'Peso' },
  { label: 'PVP' },
  {
    label: 'Promo',
    title:
      'Promoção da própria linha. Por baixo, a parte do desconto global da fatura que lhe coube — essa reparte-se sozinha a partir do desconto no cabeçalho.',
  },
  {
    label: 'Total',
    title:
      'PVP menos a promoção da linha. Por baixo, o mesmo valor já com a fatia do desconto global da fatura — esse é o que foi pago.',
  },
  {
    label: '€/kg',
    title:
      'Sobre o preço efetivamente pago, já com a promoção e o desconto global da fatura. Passe o rato para ver também o €/kg de tabela (PVP).',
  },
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
 * One figure in the reconciliation strip: label above, number below.
 *
 * The label/value pairs used to be full-width rows stacked four deep, which gave
 * three short numbers the vertical weight of a paragraph.
 */
function TotalStat({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <p
        className="text-[0.65rem] font-medium uppercase tracking-wide text-muted-foreground"
        title={hint}
      >
        {label}
      </p>
      <div className="numeric text-lg font-semibold leading-tight">{children}</div>
    </div>
  );
}

/**
 * A total that is an **input**, edited in place.
 *
 * The invoice discount is one of them: the per-line share is the proration of a
 * figure that is recomputed on every edit, so it is here that it is changed.
 */
function EditableTotalStat({
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
    <TotalStat label={label} hint={hint}>
      {draft === null ? (
        <button
          type="button"
          disabled={disabled}
          onClick={() => setDraft(value === null ? '' : String(value))}
          className="-mx-1 rounded px-1 hover:bg-muted disabled:cursor-default disabled:hover:bg-transparent"
        >
          {eur(value)}
        </button>
      ) : (
        <Input
          autoFocus
          className="h-8 w-24 text-base"
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
    </TotalStat>
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
  const reopenReceipt = useReopenReceipt();
  const confirmCategories = useConfirmReceiptCategories();
  const voidReceipt = useVoidReceipt();
  const reparse = useReparse();
  const updateItem = useUpdateItem();
  const updateReceipt = useUpdateReceipt();
  const deleteItem = useDeleteItem();
  const reassign = useReassignItemProduct();

  const [addFsOpen, setAddFsOpen] = React.useState(false);
  const [addLineOpen, setAddLineOpen] = React.useState(false);
  const [itemToRemove, setItemToRemove] = React.useState<ReceiptItem | null>(null);
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
      setItemToRemove(null);
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
    // Clearing is a real answer on the fields that may legitimately be unknown;
    // elsewhere an empty box is a slip, not an instruction.
    const cleared = raw === '' && CLEARABLE_FIELDS.includes(field);
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
        patch: { [field]: cleared ? null : field === 'line_no' ? Math.round(numeric) : numeric },
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
  // Paper order. A hand-added line has no number until someone gives it one, so
  // it waits at the end rather than jumping to the top.
  const printedItems = (receipt?.items.filter((item) => !item.is_fs) ?? [])
    .slice()
    .sort((a, b) => (a.line_no ?? Infinity) - (b.line_no ?? Infinity));
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

                <div className="border-b border-border py-4">
                  {/* The two figures being reconciled sit side by side, the input
                      that moves them next to it, and the verdict as a badge — a
                      full-width banner for one number was most of this block. */}
                  <div className="flex flex-wrap items-end gap-x-8 gap-y-3">
                    <TotalStat label="Total impresso">{eur(receipt.total_eur)}</TotalStat>
                    <TotalStat label="Soma das linhas">
                      {liveTotal !== null
                        ? eur(liveTotal)
                        : eur(receipt.derived.computed_total_eur)}
                    </TotalStat>
                    <EditableTotalStat
                      label="Desconto da fatura"
                      hint="Reparte-se por todas as linhas, que por isso não o editam uma a uma."
                      value={receipt.total_discount_eur}
                      disabled={!canEditItems}
                      onSave={(total_discount_eur) =>
                        updateReceipt.mutate({
                          receiptId: receipt.id,
                          patch: { total_discount_eur },
                        })
                      }
                    />
                    <div className="pb-1">
                      {receipt.derived.is_reconciled === false ? (
                        <Badge
                          variant="warning"
                          title="As linhas não batem certo com o total impresso."
                        >
                          <AlertTriangle />
                          {eur(receipt.derived.reconciliation_delta_eur)} de diferença
                        </Badge>
                      ) : (
                        <Badge variant="success">
                          <CheckCircle2 />
                          reconciliada
                        </Badge>
                      )}
                    </div>
                  </div>
                  {receipt.derived.fs_item_count > 0 ? (
                    <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
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
                      {printedItems.map((item) => (
                        <ItemRow
                          key={item.id}
                          {...itemRowProps(item)}
                          onRemove={canEditItems ? () => setItemToRemove(item) : undefined}
                        />
                      ))}
                    </TableBody>
                  </Table>

                  {canEditItems ? (
                    <Button size="sm" variant="outline" onClick={() => setAddLineOpen(true)}>
                      <Plus />
                      Adicionar linha
                    </Button>
                  ) : null}

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
                          {fsItems.map((item) => (
                            <ItemRow
                              key={item.id}
                              {...itemRowProps(item)}
                              onRemove={canEditItems ? () => setItemToRemove(item) : undefined}
                            />
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
                    {receipt.status === 'CONFIRMED' ? (
                      <Button
                        variant="outline"
                        title="Devolve a fatura à revisão. As observações de preço já registadas mantêm-se."
                        loading={reopenReceipt.isPending}
                        onClick={() => reopenReceipt.mutate(receipt.id)}
                      >
                        <RotateCcw />
                        Reabrir
                      </Button>
                    ) : (
                      <Button
                        disabled={locked || !receipt.derived.is_complete}
                        title={
                          receipt.derived.is_complete
                            ? 'Congela os preços desta fatura no histórico.'
                            : 'Há linhas por resolver: sem produto, a linha não entra no histórico de preços nem herda categoria.'
                        }
                        loading={confirmReceipt.isPending}
                        onClick={() => confirmReceipt.mutate(receipt.id)}
                      >
                        <CheckCircle2 />
                        Confirmar
                      </Button>
                    )}
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
                      disabled={!receipt.document_id || locked}
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
        <>
          <AddFsItemDialog receiptId={receipt.id} open={addFsOpen} onOpenChange={setAddFsOpen} />
          {/* Same dialog, printed line: the parser missed something that is on
              the paper, so it joins the sum the reconciliation checks. */}
          <AddFsItemDialog
            receiptId={receipt.id}
            open={addLineOpen}
            onOpenChange={setAddLineOpen}
            isFs={false}
          />
        </>
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
      <Dialog open={itemToRemove !== null} onOpenChange={(open) => !open && setItemToRemove(null)}>
        <DialogContent size="sm">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Trash2 className="size-4" />
              {itemToRemove?.is_fs ? 'Remover artigo Fs' : 'Remover linha'}
            </DialogTitle>
          </DialogHeader>
          <DialogBody>
            <p className="text-sm text-muted-foreground">
              <span className="font-medium text-foreground">
                {itemToRemove?.display_name ?? itemToRemove?.description_raw}
              </span>{' '}
              {itemToRemove?.is_fs
                ? 'deixa de contar para o valor nocional desta fatura. Nenhum valor impresso se altera — um artigo Fs nunca esteve na fatura.'
                : 'sai da soma das linhas e o desconto da fatura volta a ser repartido pelas restantes. Confirme a reconciliação a seguir.'}
            </p>
          </DialogBody>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setItemToRemove(null)}>
              Cancelar
            </Button>
            <Button
              variant="destructive"
              loading={deleteItem.isPending}
              onClick={async () => {
                if (!receipt || !itemToRemove) return;
                await deleteItem.mutateAsync({ receiptId: receipt.id, itemId: itemToRemove.id });
                setItemToRemove(null);
              }}
            >
              Remover
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
