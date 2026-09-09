import * as React from 'react';
import { Search, X } from 'lucide-react';
import { PageHeader } from '@/components/ui/feedback';
import { Button } from '@/components/ui/button';
import { DateInput, Input } from '@/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/primitives';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useSession } from '@/features/auth/session';
import { useDebounced, useUrlFilters } from '@/lib/filters';
import { RECEIPT_STATUS_OPTIONS } from '@/features/supermarket/constants';
import { useReceiptItems, useProductSummary, useReceipts } from '@/features/supermarket/api';
import { ReceiptStatusPanel } from '@/features/supermarket/status-panel';
import { ReceiptUploadDialog } from '@/features/supermarket/upload-panel';
import { ReceiptQueueTable } from '@/features/supermarket/queue-table';
import { ReceiptsTable } from '@/features/supermarket/receipts-table';
import { ReceiptItemsTable } from '@/features/supermarket/items-table';
import { ProductSummaryTable } from '@/features/supermarket/product-summary-table';
import { ParserProfilesPanel } from '@/features/supermarket/parser-profiles-panel';
import { ReceiptReviewPane } from '@/features/supermarket/review-pane';
import { PriceEvolutionPanel } from '@/features/supermarket/price-evolution-panel';
import { SpendPanel } from '@/features/supermarket/spend-panel';
import { LoyaltyPanel } from '@/features/supermarket/loyalty-panel';
import { ProductsPanel } from '@/features/supermarket/products-panel';
import { CategoriesPanel } from '@/features/supermarket/categories-panel';
import { LegacyImportPanel } from '@/features/supermarket/legacy-import-panel';

const ALL = '__all__';

const DEFAULTS = {
  tab: 'estado',
  search: undefined,
  merchant_id: undefined,
  status: undefined,
  date_from: undefined,
  date_to: undefined,
  //: Which reading of the Artigos tab is open, and which product it drilled into.
  view: 'detalhe',
  product: undefined,
  page: '1',
  page_size: '25',
  //: Which invoice the review pane is open on, so the shared Review Queue can
  //: deep-link straight into it (ADR-0025) and the screen stays bookmarkable.
  receipt: undefined,
} satisfies Record<string, string | undefined>;

function FilterBar({
  filters,
  setFilters,
  showStatus,
}: {
  filters: Record<string, string | undefined>;
  setFilters: (patch: Record<string, string | undefined>) => void;
  showStatus: boolean;
}) {
  const [searchDraft, setSearchDraft] = React.useState(filters.search ?? '');
  const debouncedSearch = useDebounced(searchDraft, 350);

  React.useEffect(() => setSearchDraft(filters.search ?? ''), [filters.search]);

  React.useEffect(() => {
    if ((filters.search ?? '') !== debouncedSearch) {
      setFilters({ search: debouncedSearch || undefined, page: '1' });
    }
  }, [debouncedSearch, filters.search, setFilters]);

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-xl border border-border bg-card p-3">
      <div className="relative min-w-[15rem] flex-1">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          className="pl-9"
          placeholder="Procurar por comerciante ou descrição…"
          value={searchDraft}
          onChange={(event) => setSearchDraft(event.target.value)}
        />
      </div>

      {showStatus ? (
        <Select
          value={filters.status ?? ALL}
          onValueChange={(value) =>
            setFilters({ status: value === ALL ? undefined : value, page: '1' })
          }
        >
          <SelectTrigger className="w-48 shrink-0">
            <SelectValue placeholder="Estado" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Qualquer estado</SelectItem>
            {RECEIPT_STATUS_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      ) : null}

      <div className="flex shrink-0 items-center gap-2">
        <DateInput
          aria-label="De"
          className="w-40"
          value={filters.date_from ?? ''}
          onChange={(iso) => setFilters({ date_from: iso || undefined, page: '1' })}
        />
        <span className="text-muted-foreground">–</span>
        <DateInput
          aria-label="Até"
          className="w-40"
          value={filters.date_to ?? ''}
          onChange={(iso) => setFilters({ date_to: iso || undefined, page: '1' })}
        />
      </div>
    </div>
  );
}

export function SupermercadoPage() {
  const { canWrite } = useSession();
  const [filters, setFilters] = useUrlFilters(DEFAULTS);

  const tab = filters.tab ?? 'estado';
  const selectedReceiptId = filters.receipt ?? null;

  const receipts = useReceipts({
    search: filters.search,
    status: filters.status,
    date_from: filters.date_from,
    date_to: filters.date_to,
    page: filters.page,
    page_size: filters.page_size,
  });

  const items = useReceiptItems({
    search: filters.search,
    date_from: filters.date_from,
    date_to: filters.date_to,
    master_product_id: filters.product,
    page: filters.page,
    page_size: filters.page_size,
  });

  const itemView = filters.view ?? 'detalhe';
  const summary = useProductSummary(
    {
      search: filters.search,
      date_from: filters.date_from,
      date_to: filters.date_to,
      page: filters.page,
      page_size: filters.page_size,
    },
    itemView === 'resumo',
  );

  const openReceipt = React.useCallback(
    (receiptId: string) => setFilters({ receipt: receiptId }, { resetPage: false }),
    [setFilters],
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Supermercado"
        description="Faturas de supermercado, do carregamento à validação linha a linha."
        actions={canWrite ? <ReceiptUploadDialog /> : null}
      />

      <Tabs value={tab} onValueChange={(value) => setFilters({ tab: value })}>
        <TabsList>
          <TabsTrigger value="estado">Estado</TabsTrigger>
          <TabsTrigger value="processamento">Processamento</TabsTrigger>
          <TabsTrigger value="faturas">Faturas</TabsTrigger>
          <TabsTrigger value="artigos">Artigos</TabsTrigger>
          <TabsTrigger value="precos">Preços</TabsTrigger>
          <TabsTrigger value="despesa">Despesa</TabsTrigger>
          <TabsTrigger value="fidelizacao">Fidelização</TabsTrigger>
          <TabsTrigger value="produtos">Produtos</TabsTrigger>
          <TabsTrigger value="categorias">Categorias</TabsTrigger>
          {canWrite ? <TabsTrigger value="importar">Importar folha</TabsTrigger> : null}
          <TabsTrigger value="perfis">Perfis de leitura</TabsTrigger>
        </TabsList>

        <TabsContent value="estado">
          <ReceiptStatusPanel
            onNavigate={(nextTab, patch) => setFilters({ tab: nextTab, page: '1', ...patch })}
          />
        </TabsContent>

        {/* The *processing* queue: one row per parse job. Everything a human has
            to decide lives in the single shared Review Queue at /revisao. */}
        <TabsContent value="processamento">
          <ReceiptQueueTable onOpen={openReceipt} />
        </TabsContent>

        <TabsContent value="faturas" className="space-y-4">
          <FilterBar filters={filters} setFilters={setFilters} showStatus />
          <ReceiptsTable
            data={receipts.data}
            isLoading={receipts.isLoading}
            onOpen={openReceipt}
            onPageChange={(page) => setFilters({ page: String(page) })}
            onPageSizeChange={(pageSize) => setFilters({ page_size: String(pageSize), page: '1' })}
          />
        </TabsContent>

        <TabsContent value="artigos" className="space-y-4">
          <FilterBar filters={filters} setFilters={setFilters} showStatus={false} />
          <div className="flex flex-wrap items-center gap-2">
            <Tabs
              value={itemView}
              onValueChange={(value) => setFilters({ view: value, product: undefined, page: '1' })}
            >
              <TabsList>
                <TabsTrigger value="detalhe">Detalhe</TabsTrigger>
                <TabsTrigger value="resumo">Resumo por produto</TabsTrigger>
              </TabsList>
            </Tabs>
            {filters.product ? (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setFilters({ product: undefined, view: 'resumo', page: '1' })}
              >
                <X />
                Voltar ao resumo
              </Button>
            ) : null}
          </div>
          {itemView === 'resumo' ? (
            <ProductSummaryTable
              data={summary.data}
              isLoading={summary.isLoading}
              onDrillDown={(productId) =>
                setFilters({ product: productId, view: 'detalhe', page: '1' })
              }
              onPageChange={(page) => setFilters({ page: String(page) })}
            />
          ) : (
            <ReceiptItemsTable
              data={items.data}
              isLoading={items.isLoading}
              onOpenReceipt={openReceipt}
              onPageChange={(page) => setFilters({ page: String(page) })}
              onPageSizeChange={(pageSize) =>
                setFilters({ page_size: String(pageSize), page: '1' })
              }
            />
          )}
        </TabsContent>

        <TabsContent value="precos">
          <PriceEvolutionPanel />
        </TabsContent>

        <TabsContent value="despesa">
          <SpendPanel />
        </TabsContent>

        <TabsContent value="fidelizacao">
          <LoyaltyPanel onOpenReceipt={openReceipt} />
        </TabsContent>

        <TabsContent value="produtos">
          <ProductsPanel onOpenReceipt={openReceipt} />
        </TabsContent>

        <TabsContent value="categorias">
          <CategoriesPanel />
        </TabsContent>

        {canWrite ? (
          <TabsContent value="importar">
            <LegacyImportPanel />
          </TabsContent>
        ) : null}

        <TabsContent value="perfis">
          <ParserProfilesPanel />
        </TabsContent>
      </Tabs>

      <ReceiptReviewPane
        receiptId={selectedReceiptId}
        onClose={() => setFilters({ receipt: undefined }, { resetPage: false })}
      />
    </div>
  );
}
