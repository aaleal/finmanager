import { ChevronsLeft, ChevronsRight, ExternalLink } from 'lucide-react';
import type { Page, ReceiptItem } from '@/lib/types';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { EmptyState, Skeleton } from '@/components/ui/feedback';
import { EM_DASH, eur, num, quantity, weightKg } from '@/lib/format';

const PAGE_SIZES = ['25', '50', '100', '200'];

export function ReceiptItemsTable({
  data,
  isLoading,
  onOpenReceipt,
  onPageChange,
  onPageSizeChange,
}: {
  data: Page<ReceiptItem> | undefined;
  isLoading: boolean;
  onOpenReceipt: (receiptId: string) => void;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
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
    return <EmptyState title="Sem artigos para os filtros escolhidos." />;
  }

  return (
    <div className="space-y-4">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Produto</TableHead>
            <TableHead>Categoria</TableHead>
            <TableHead>Qtd</TableHead>
            <TableHead>Peso</TableHead>
            <TableHead>PVP</TableHead>
            <TableHead>Promo</TableHead>
            <TableHead>Pago</TableHead>
            <TableHead>€/kg</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.items.map((item) => (
            <TableRow key={item.id}>
              <TableCell className="max-w-[16rem]">
                <span className="flex items-center gap-1.5">
                  <span className="truncate" title={item.description_raw}>
                    {item.display_name ?? item.description_raw}
                  </span>
                  {item.is_fs ? <Badge variant="outline">Fs</Badge> : null}
                </span>
              </TableCell>
              <TableCell className="max-w-[14rem] truncate" title={item.category_path ?? undefined}>
                {item.category_path ?? EM_DASH}
              </TableCell>
              <TableCell className="numeric" title={`${item.quantity} ${item.unit}`}>
                {quantity(item.quantity, { soldByWeight: item.sold_by_weight })}
              </TableCell>
              <TableCell className="numeric">{weightKg(item.weight_kg)}</TableCell>
              <TableCell className="numeric">{eur(item.unit_price_pvp_eur)}</TableCell>
              <TableCell className="numeric">{eur(item.promo_discount_eur)}</TableCell>
              <TableCell className="numeric font-medium">{eur(item.paid_price_eur)}</TableCell>
              <TableCell className="numeric">
                {item.price_per_kg_final_eur ? (
                  eur(item.price_per_kg_final_eur)
                ) : (
                  <span title={item.price_per_kg_unavailable_reason ?? undefined}>{EM_DASH}</span>
                )}
              </TableCell>
              <TableCell>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  title="Abrir a fatura"
                  onClick={() => onOpenReceipt(item.receipt_id)}
                >
                  <ExternalLink />
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <div className="flex flex-wrap items-center justify-between gap-4 text-sm">
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground">Linhas por página</span>
          <Select
            value={String(pageSize)}
            onValueChange={(value) => onPageSizeChange(Number(value))}
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
            {data.total === 0
              ? 'sem resultados'
              : `${num((page - 1) * pageSize + 1)}–${num(Math.min(page * pageSize, data.total))} de ${num(data.total)}`}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => onPageChange(1)}
            aria-label="Primeira página"
          >
            <ChevronsLeft />
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
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
            onClick={() => onPageChange(page + 1)}
          >
            Seguinte
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => onPageChange(totalPages)}
            aria-label="Última página"
          >
            <ChevronsRight />
          </Button>
        </div>
      </div>
    </div>
  );
}
