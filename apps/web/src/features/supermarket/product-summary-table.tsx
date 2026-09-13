import { ChevronsLeft, ChevronsRight, ListTree } from 'lucide-react';
import type { Page, ProductSummary } from '@/lib/types';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { EmptyState, Skeleton } from '@/components/ui/feedback';
import { EM_DASH, date, eur, num, quantity, weightCompact } from '@/lib/format';
import { AttributeBadges } from './product-attributes';

/**
 * The same purchases as the detail view, grouped by product.
 *
 * Answers *«quanto comprei disto ao todo»*, which the line-by-line view cannot:
 * there, ten purchases of the same thing are ten unrelated rows.
 */
export function ProductSummaryTable({
  data,
  isLoading,
  onDrillDown,
  onPageChange,
}: {
  data: Page<ProductSummary> | undefined;
  isLoading: boolean;
  onDrillDown: (productId: string) => void;
  onPageChange: (page: number) => void;
}) {
  const page = data?.page ?? 1;
  const pageSize = data?.page_size ?? 50;
  const totalPages = data ? Math.max(1, Math.ceil(data.total / pageSize)) : 1;

  if (isLoading && !data) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 6 }).map((_, index) => (
          <Skeleton key={index} className="h-12 rounded-lg" />
        ))}
      </div>
    );
  }

  if (!data?.items.length) {
    return <EmptyState title="Sem produtos para os filtros escolhidos." />;
  }

  return (
    <div className="space-y-4">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Produto</TableHead>
            <TableHead>Categoria</TableHead>
            <TableHead title="Faturas em que aparece / linhas no total">Compras</TableHead>
            <TableHead>Qtd</TableHead>
            <TableHead>Peso</TableHead>
            <TableHead title="Fs incluído ao seu valor nocional.">Total</TableHead>
            <TableHead title="Ponderado pelo peso, não a média dos €/kg de cada compra. Linhas sem peso ficam de fora.">
              €/kg
            </TableHead>
            <TableHead>Última</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.items.map((row) => (
            <TableRow
              key={row.master_product_id}
              className="cursor-pointer"
              onClick={() => onDrillDown(row.master_product_id)}
            >
              <TableCell className="max-w-[16rem]">
                <span className="block truncate font-medium">{row.canonical_name}</span>
                <span className="block truncate text-xs text-muted-foreground">
                  {row.brand ?? EM_DASH}
                </span>
                <AttributeBadges
                  className="mt-1"
                  isOwnBrand={row.is_own_brand}
                  conservation={row.conservation}
                  presentation={row.presentation}
                  dietary={row.dietary_attributes}
                />
              </TableCell>
              <TableCell
                className="max-w-[14rem] truncate text-xs"
                title={row.category_path ?? undefined}
              >
                {row.category_path ?? EM_DASH}
              </TableCell>
              <TableCell className="numeric" title={`${row.line_count} linhas`}>
                {num(row.receipt_count)}
              </TableCell>
              <TableCell className="numeric">
                {quantity(row.total_quantity, { soldByWeight: row.sold_by_weight })}
              </TableCell>
              <TableCell className="numeric">{weightCompact(row.total_weight_kg)}</TableCell>
              <TableCell className="numeric font-medium">{eur(row.total_notional_eur)}</TableCell>
              <TableCell className="numeric">{eur(row.price_per_kg_eur)}</TableCell>
              <TableCell className="whitespace-nowrap text-xs">
                {date(row.last_purchase_on)}
              </TableCell>
              <TableCell>
                <Button variant="ghost" size="icon-sm" title="Ver cada compra deste produto">
                  <ListTree />
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <div className="flex flex-wrap items-center justify-between gap-4 text-sm">
        <span className="text-muted-foreground">
          {data.total === 0 ? 'sem resultados' : `${num(data.total)} produtos`}
        </span>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
            aria-label="Página anterior"
          >
            <ChevronsLeft />
          </Button>
          <span className="text-muted-foreground">
            {num(page)} / {num(totalPages)}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => onPageChange(page + 1)}
            aria-label="Página seguinte"
          >
            <ChevronsRight />
          </Button>
        </div>
      </div>
    </div>
  );
}
