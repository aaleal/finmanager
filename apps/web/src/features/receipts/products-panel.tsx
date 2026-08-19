import * as React from 'react';
import {
  CheckCircle2,
  ChevronsLeft,
  ChevronsRight,
  ExternalLink,
  GitMerge,
  HelpCircle,
  Pencil,
  Plus,
  Scale,
  Search,
  Trash2,
} from 'lucide-react';
import type { components } from '@/api/schema';
import type { CategoryResult, MasterProduct } from '@/lib/types';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Field, Input } from '@/components/ui/input';
import { Dialog, SheetContent } from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Switch, Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/primitives';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { DetailRow, EmptyState, Skeleton } from '@/components/ui/feedback';
import { date, EM_DASH, eur, num, packLabel, percent } from '@/lib/format';
import { useDebounced } from '@/lib/filters';
import { useSession } from '@/features/auth/session';
import { CategoryPicker } from './category-picker';
import { ProductCreateDialog } from './product-create-dialog';
import {
  useMergeCandidates,
  useMergeProducts,
  useProduct,
  useProductAliases,
  useProductOccurrences,
  useProducts,
  useUpdateProduct,
  useValidateProductCategory,
} from './catalogue-api';

type PackVariant = components['schemas']['PackVariant'];

const ALL = '__all__';
const PAGE_SIZES = ['25', '50', '100'];

const CATEGORY_STATUS_OPTIONS = [
  { value: ALL, label: 'Todos' },
  { value: 'AUTO', label: 'Por confirmar (AUTO)' },
  { value: 'VALIDATED', label: 'Confirmada' },
  { value: 'MANUAL', label: 'Manual' },
];

const CATEGORY_STATUS_META: Record<
  string,
  { label: string; icon: typeof CheckCircle2; variant: 'warning' | 'success' | 'muted' }
> = {
  AUTO: { label: 'por confirmar', icon: HelpCircle, variant: 'warning' },
  VALIDATED: { label: 'confirmada', icon: CheckCircle2, variant: 'success' },
  MANUAL: { label: 'manual', icon: Pencil, variant: 'muted' },
};

function categoryConfidencePct(value: string | null): number | null {
  if (value === null) return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric * 100 : null;
}

type WeightUnit = 'g' | 'kg';

/** A format as it is edited: the number and the unit the human chose to say it in. */
type VariantRow = { value: string; unit: WeightUnit; label: string; barcode: string | null };

function variantToRow(variant: PackVariant): VariantRow {
  const kg = Number(variant.weight_kg ?? '');
  const known = Number.isFinite(kg) && kg > 0;
  const unit: WeightUnit = known && kg < 1 ? 'g' : 'kg';
  return {
    value: !known ? '' : unit === 'g' ? String(Math.round(kg * 1000)) : String(kg),
    unit,
    label: variant.label ?? '',
    barcode: variant.barcode ?? null,
  };
}

/** The gram is the smallest format anyone shops in, so kg never carries a fourth decimal. */
function rowWeightKg(row: VariantRow): string | null {
  const raw = row.value.trim().replace(',', '.');
  if (!raw) return null;
  const numeric = Number(raw);
  if (!Number.isFinite(numeric) || numeric <= 0) return null;
  const grams = Math.round(row.unit === 'g' ? numeric : numeric * 1000);
  return grams > 0 ? (grams / 1000).toFixed(3) : null;
}

function isBlankRow(row: VariantRow): boolean {
  return !row.value.trim() && !row.label.trim();
}

function rowsToVariants(rows: VariantRow[]): PackVariant[] {
  return rows.filter((row) => !isBlankRow(row)).map((row) => ({
    label: row.label.trim() || null,
    weight_kg: rowWeightKg(row),
    barcode: row.barcode,
  }));
}

/** Unique weights are what let a receipt line find its format by value alone. */
function packVariantsError(rows: VariantRow[]): string | null {
  const weights: string[] = [];
  for (const row of rows) {
    if (isBlankRow(row)) continue;
    const weight = rowWeightKg(row);
    if (weight === null) return 'Cada formato precisa de um peso maior do que zero.';
    if (weights.includes(weight)) return `O formato ${packLabel(weight)} está repetido.`;
    weights.push(weight);
  }
  return null;
}

function MergeCandidatesSection() {
  const candidates = useMergeCandidates();
  const merge = useMergeProducts();
  const [targets, setTargets] = React.useState<Record<string, string>>({});

  const groups = candidates.data ?? [];
  if (!candidates.isLoading && !groups.length) return null;

  return (
    <div className="space-y-3 rounded-xl border border-warning/30 bg-warning/5 p-4">
      <div>
        <p className="text-sm font-semibold">Produtos a fundir</p>
        <p className="text-xs text-muted-foreground">
          Nomes canónicos quase idênticos — escolha o produto sobrevivente e funda os restantes.
        </p>
      </div>
      {candidates.isLoading ? (
        <Skeleton className="h-16 rounded-lg" />
      ) : (
        groups.map((group) => {
          const products = group.products;
          const targetId = targets[group.key] ?? products[0]?.id;
          return (
            <div key={group.key} className="space-y-2 rounded-lg border border-border bg-card p-3">
              {products.map((product) => (
                <div key={product.id} className="flex items-center gap-3 text-sm">
                  <label className="flex flex-1 items-center gap-2">
                    <input
                      type="radio"
                      name={`survivor-${group.key}`}
                      checked={targetId === product.id}
                      onChange={() =>
                        setTargets((previous) => ({ ...previous, [group.key]: product.id }))
                      }
                    />
                    <span className="font-medium">{product.canonical_name}</span>
                    <span className="text-xs text-muted-foreground">
                      {product.brand ?? EM_DASH}
                    </span>
                  </label>
                  {targetId !== product.id ? (
                    <Button
                      size="sm"
                      variant="outline"
                      loading={merge.isPending}
                      onClick={() => merge.mutate({ targetId, sourceId: product.id })}
                    >
                      <GitMerge />
                      Fundir
                    </Button>
                  ) : (
                    <Badge variant="outline">sobrevivente</Badge>
                  )}
                </div>
              ))}
            </div>
          );
        })
      )}
    </div>
  );
}

function PackVariantsEditor({
  rows,
  disabled,
  onChange,
}: {
  rows: VariantRow[];
  disabled: boolean;
  onChange: (rows: VariantRow[]) => void;
}) {
  function update(index: number, patch: Partial<VariantRow>) {
    onChange(rows.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  }

  const error = packVariantsError(rows);

  return (
    <div className="space-y-2">
      {rows.map((row, index) => {
        const weight = rowWeightKg(row);
        return (
          <div key={index} className="flex items-end gap-2">
            <Field label="Peso" className="w-28">
              <Input
                inputMode="decimal"
                placeholder={row.unit === 'g' ? '500' : '1,5'}
                value={row.value}
                disabled={disabled}
                onChange={(event) => update(index, { value: event.target.value })}
              />
            </Field>
            <Select
              value={row.unit}
              disabled={disabled}
              onValueChange={(unit) => update(index, { unit: unit as WeightUnit })}
            >
              <SelectTrigger className="w-20" aria-label="Unidade">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="g">g</SelectItem>
                <SelectItem value="kg">kg</SelectItem>
              </SelectContent>
            </Select>
            <Field label="Nome (opcional)" className="flex-1">
              <Input
                value={row.label}
                placeholder={weight ? packLabel(weight, '') : 'derivado do peso'}
                disabled={disabled}
                onChange={(event) => update(index, { label: event.target.value })}
              />
            </Field>
            <Button
              variant="ghost"
              size="icon-sm"
              disabled={disabled}
              onClick={() => onChange(rows.filter((_, i) => i !== index))}
              aria-label="Remover formato"
            >
              <Trash2 />
            </Button>
          </div>
        );
      })}
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={disabled}
        onClick={() => onChange([...rows, { value: '', unit: 'g', label: '', barcode: null }])}
      >
        <Plus />
        Adicionar formato
      </Button>
      {error ? <p className="text-xs text-destructive">{error}</p> : null}
    </div>
  );
}

function ProductDetailsTab({ product }: { product: MasterProduct }) {
  const { canWrite } = useSession();
  const update = useUpdateProduct();
  const [name, setName] = React.useState(product.canonical_name);
  const [brand, setBrand] = React.useState(product.brand ?? '');
  const [category, setCategory] = React.useState<CategoryResult | null>(null);
  const [soldByWeight, setSoldByWeight] = React.useState(product.sold_by_weight);
  const [packRows, setPackRows] = React.useState<VariantRow[]>(() =>
    ((product.pack_variants as PackVariant[]) ?? []).map(variantToRow),
  );

  React.useEffect(() => {
    setName(product.canonical_name);
    setBrand(product.brand ?? '');
    setCategory(null);
    setSoldByWeight(product.sold_by_weight);
    setPackRows(((product.pack_variants as PackVariant[]) ?? []).map(variantToRow));
  }, [product]);

  const categoryPath = category?.path ?? product.category_path ?? null;
  const price = product.last_known_price;
  const packError = packVariantsError(packRows);

  return (
    <div className="space-y-4">
      <Field label="Nome canónico">
        <Input
          value={name}
          onChange={(event) => setName(event.target.value)}
          disabled={!canWrite}
        />
      </Field>
      <Field label="Marca">
        <Input
          value={brand}
          onChange={(event) => setBrand(event.target.value)}
          disabled={!canWrite}
        />
      </Field>
      <Field label="Categoria">
        <CategoryPicker value={categoryPath} onSelect={setCategory} disabled={!canWrite} />
      </Field>
      <div className="flex items-center justify-between rounded-lg border border-border px-3 py-2">
        <div className="flex items-center gap-2 text-sm">
          <Scale className="size-4 text-muted-foreground" />
          Vendido a peso
        </div>
        <Switch checked={soldByWeight} onCheckedChange={setSoldByWeight} disabled={!canWrite} />
      </div>
      <Field
        label="Formatos de embalagem"
        hint="Os pesos oficiais deste produto. O que a fatura trouxer é comparado com esta lista."
      >
        <PackVariantsEditor rows={packRows} disabled={!canWrite} onChange={setPackRows} />
      </Field>

      <div className="rounded-lg border border-border bg-muted/30 p-3 text-sm">
        {price?.last_pvp_eur ? (
          <dl className="space-y-1">
            <DetailRow label="Último PVP">{eur(price.last_pvp_eur)}</DetailRow>
            <DetailRow label="Último €/kg">{eur(price.last_price_per_kg_eur)}</DetailRow>
            <DetailRow label="Observado em">{date(price.last_observed_on)}</DetailRow>
          </dl>
        ) : (
          <p className="text-muted-foreground">Sem observações de preço ainda.</p>
        )}
      </div>

      {canWrite ? (
        <Button
          loading={update.isPending}
          disabled={packError !== null}
          onClick={() =>
            update.mutate({
              productId: product.id,
              patch: {
                canonical_name: name.trim(),
                brand: brand.trim() || null,
                category_id: category ? category.id : product.category_id,
                sold_by_weight: soldByWeight,
                pack_variants: rowsToVariants(packRows),
              },
            })
          }
        >
          Guardar alterações
        </Button>
      ) : null}
    </div>
  );
}

function ProductAliasesTab({ productId }: { productId: string }) {
  const aliases = useProductAliases(productId);

  if (aliases.isLoading) return <Skeleton className="h-32 rounded-lg" />;
  if (!aliases.data?.length)
    return <EmptyState title="Sem aliases aprendidos para este produto." />;

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Comerciante</TableHead>
          <TableHead>Texto do comerciante</TableHead>
          <TableHead>Confiança</TableHead>
          <TableHead>Correções</TableHead>
          <TableHead>Última utilização</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {aliases.data.map((alias) => (
          <TableRow key={alias.id}>
            <TableCell>{alias.merchant_name ?? EM_DASH}</TableCell>
            <TableCell className="max-w-[14rem] truncate" title={alias.merchant_description}>
              {alias.merchant_description}
            </TableCell>
            <TableCell className="numeric">{percent(Number(alias.confidence) * 100)}</TableCell>
            <TableCell className="numeric">{num(alias.correction_count)}</TableCell>
            <TableCell>{date(alias.last_used_at)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function ProductOccurrencesTab({
  productId,
  onOpenReceipt,
}: {
  productId: string;
  onOpenReceipt: (receiptId: string) => void;
}) {
  const occurrences = useProductOccurrences(productId);

  if (occurrences.isLoading) return <Skeleton className="h-32 rounded-lg" />;
  if (!occurrences.data?.length)
    return <EmptyState title="Sem ocorrências deste produto em faturas." />;

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Data</TableHead>
          <TableHead>Comerciante</TableHead>
          <TableHead>Descrição no talão</TableHead>
          <TableHead>Qtd</TableHead>
          <TableHead>PVP</TableHead>
          <TableHead>Pago</TableHead>
          <TableHead>€/kg</TableHead>
          <TableHead />
        </TableRow>
      </TableHeader>
      <TableBody>
        {occurrences.data.map((occurrence) => (
          <TableRow key={occurrence.receipt_item_id}>
            <TableCell>{date(occurrence.purchase_date)}</TableCell>
            <TableCell>{occurrence.merchant_name ?? EM_DASH}</TableCell>
            <TableCell className="max-w-[14rem] truncate" title={occurrence.description_raw}>
              <span className="flex items-center gap-1.5">
                {occurrence.description_raw}
                {occurrence.is_fs ? <Badge variant="outline">Fs</Badge> : null}
              </span>
            </TableCell>
            <TableCell className="numeric">
              {occurrence.quantity} {occurrence.unit}
            </TableCell>
            <TableCell className="numeric">{eur(occurrence.unit_price_pvp_eur)}</TableCell>
            <TableCell className="numeric">{eur(occurrence.paid_price_eur)}</TableCell>
            <TableCell className="numeric">{eur(occurrence.price_per_kg_final_eur)}</TableCell>
            <TableCell>
              <Button
                variant="ghost"
                size="icon-sm"
                title="Abrir a fatura"
                onClick={() => onOpenReceipt(occurrence.receipt_id)}
              >
                <ExternalLink />
              </Button>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function ProductDetailSheet({
  productId,
  onClose,
  onOpenReceipt,
}: {
  productId: string | null;
  onClose: () => void;
  onOpenReceipt: (receiptId: string) => void;
}) {
  const product = useProduct(productId);

  return (
    <Dialog open={Boolean(productId)} onOpenChange={(open) => !open && onClose()}>
      <SheetContent width="md">
        {product.isLoading || !product.data ? (
          <div className="space-y-3 p-6">
            <Skeleton className="h-8" />
            <Skeleton className="h-64" />
          </div>
        ) : (
          <div className="flex h-full flex-col overflow-y-auto px-6 py-5 pr-12">
            <h2 className="text-lg font-semibold leading-tight">{product.data.canonical_name}</h2>
            <Tabs defaultValue="detalhes" className="mt-4">
              <TabsList>
                <TabsTrigger value="detalhes">Detalhes</TabsTrigger>
                <TabsTrigger value="aliases">Aliases</TabsTrigger>
                <TabsTrigger value="ocorrencias">Ocorrências</TabsTrigger>
              </TabsList>
              <TabsContent value="detalhes">
                <ProductDetailsTab product={product.data} />
              </TabsContent>
              <TabsContent value="aliases">
                <ProductAliasesTab productId={product.data.id} />
              </TabsContent>
              <TabsContent value="ocorrencias">
                <ProductOccurrencesTab productId={product.data.id} onOpenReceipt={onOpenReceipt} />
              </TabsContent>
            </Tabs>
          </div>
        )}
      </SheetContent>
    </Dialog>
  );
}

export function ProductsPanel({ onOpenReceipt }: { onOpenReceipt: (receiptId: string) => void }) {
  const { canWrite } = useSession();
  const [searchDraft, setSearchDraft] = React.useState('');
  const debouncedSearch = useDebounced(searchDraft, 350);
  const [categoryStatus, setCategoryStatus] = React.useState(ALL);
  const [category, setCategory] = React.useState<CategoryResult | null>(null);
  const [page, setPage] = React.useState(1);
  const [pageSize, setPageSize] = React.useState(50);
  const [selectedProductId, setSelectedProductId] = React.useState<string | null>(null);
  const [createOpen, setCreateOpen] = React.useState(false);

  React.useEffect(() => setPage(1), [debouncedSearch, categoryStatus, category]);

  const products = useProducts({
    search: debouncedSearch || undefined,
    category_status: categoryStatus === ALL ? undefined : categoryStatus,
    category_id: category?.id,
    page: String(page),
    page_size: String(pageSize),
  });

  const validateCategory = useValidateProductCategory();

  const total = products.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="space-y-4">
      {canWrite ? (
        <div className="flex justify-end">
          <Button onClick={() => setCreateOpen(true)}>
            <Plus />
            Novo produto
          </Button>
        </div>
      ) : null}

      <MergeCandidatesSection />

      <div className="grid gap-3 rounded-xl border border-border bg-card p-4 sm:grid-cols-3">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-9"
            placeholder="Procurar por nome ou marca…"
            value={searchDraft}
            onChange={(event) => setSearchDraft(event.target.value)}
          />
        </div>
        <Select value={categoryStatus} onValueChange={setCategoryStatus}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {CATEGORY_STATUS_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <CategoryPicker
          value={category?.path ?? null}
          onSelect={setCategory}
          allowClear
          placeholder="Filtrar por categoria…"
        />
      </div>

      {products.isLoading && !products.data ? (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} className="h-12 rounded-lg" />
          ))}
        </div>
      ) : !products.data?.items.length ? (
        <EmptyState title="Sem produtos para os filtros escolhidos." />
      ) : (
        <div className="space-y-4">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Nome canónico</TableHead>
                <TableHead>Marca</TableHead>
                <TableHead>Categoria</TableHead>
                <TableHead>Estado</TableHead>
                <TableHead>Confiança</TableHead>
                <TableHead>A peso</TableHead>
                <TableHead>Aliases</TableHead>
                <TableHead>Ocorrências</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {products.data.items.map((product) => {
                const meta =
                  CATEGORY_STATUS_META[product.category_status] ?? CATEGORY_STATUS_META.AUTO;
                const StatusIcon = meta.icon;
                return (
                  <TableRow
                    key={product.id}
                    className="cursor-pointer"
                    onClick={() => setSelectedProductId(product.id)}
                  >
                    <TableCell className="font-medium">{product.canonical_name}</TableCell>
                    <TableCell>{product.brand ?? EM_DASH}</TableCell>
                    <TableCell
                      className="max-w-[12rem] truncate"
                      title={product.category_path ?? undefined}
                    >
                      {product.category_path ?? EM_DASH}
                    </TableCell>
                    <TableCell>
                      <Badge variant={meta.variant}>
                        <StatusIcon />
                        {meta.label}
                      </Badge>
                    </TableCell>
                    <TableCell className="numeric">
                      {percent(categoryConfidencePct(product.category_confidence))}
                    </TableCell>
                    <TableCell>
                      {product.sold_by_weight ? (
                        <span className="flex items-center gap-1 text-xs text-muted-foreground">
                          <Scale className="size-3.5" />a peso
                        </span>
                      ) : (
                        EM_DASH
                      )}
                    </TableCell>
                    <TableCell className="numeric">{num(product.alias_count)}</TableCell>
                    <TableCell className="numeric">{num(product.occurrence_count)}</TableCell>
                    <TableCell>
                      {canWrite && product.category_status === 'AUTO' ? (
                        <Button
                          size="sm"
                          variant="outline"
                          loading={validateCategory.isPending}
                          onClick={(event) => {
                            event.stopPropagation();
                            validateCategory.mutate(product.id);
                          }}
                        >
                          <CheckCircle2 />
                          Confirmar categoria
                        </Button>
                      ) : null}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>

          <div className="flex flex-wrap items-center justify-between gap-4 text-sm">
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground">Linhas por página</span>
              <Select
                value={String(pageSize)}
                onValueChange={(value) => {
                  setPageSize(Number(value));
                  setPage(1);
                }}
              >
                <SelectTrigger className="h-8 w-[4.5rem]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PAGE_SIZES.map((size) => (
                    <SelectItem key={size} value={size}>
                      {size}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <span className="text-muted-foreground">
                {total === 0
                  ? 'sem resultados'
                  : `${num((page - 1) * pageSize + 1)}–${num(Math.min(page * pageSize, total))} de ${num(total)}`}
              </span>
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage(1)}
                aria-label="Primeira página"
              >
                <ChevronsLeft />
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                Anterior
              </Button>
              <span className="text-muted-foreground">
                {page} / {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                Seguinte
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= totalPages}
                onClick={() => setPage(totalPages)}
                aria-label="Última página"
              >
                <ChevronsRight />
              </Button>
            </div>
          </div>
        </div>
      )}

      <ProductDetailSheet
        productId={selectedProductId}
        onClose={() => setSelectedProductId(null)}
        onOpenReceipt={onOpenReceipt}
      />

      <ProductCreateDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={(product) => setSelectedProductId(product.id)}
      />
    </div>
  );
}
