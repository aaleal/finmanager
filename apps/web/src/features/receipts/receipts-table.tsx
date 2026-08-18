import { CheckCircle2, ChevronsLeft, ChevronsRight, XCircle } from 'lucide-react';
import type { Page, ReceiptSummary } from '@/lib/types';
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
import { EM_DASH, date, eur, num, percent } from '@/lib/format';
import { RECEIPT_STATUS_META } from './constants';

const PAGE_SIZES = ['10', '25', '50', '100'];

export function ReceiptsTable({
  data,
  isLoading,
  onOpen,
  onPageChange,
  onPageSizeChange,
}: {
  data: Page<ReceiptSummary> | undefined;
  isLoading: boolean;
  onOpen: (id: string) => void;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
}) {
  const page = data?.page ?? 1;
  const pageSize = data?.page_size ?? 25;
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
    return <EmptyState title="Sem faturas para os filtros escolhidos." />;
  }

  return (
    <div className="space-y-4">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Data</TableHead>
            <TableHead>Comerciante</TableHead>
            <TableHead>Perfil de leitura</TableHead>
            <TableHead>Total</TableHead>
            <TableHead>Valor Fs</TableHead>
            <TableHead>Total nocional</TableHead>
            <TableHead title="Artigos impressos na fatura / artigos Fs acrescentados à mão">
              Artigos
            </TableHead>
            <TableHead>Estado</TableHead>
            <TableHead>Reconciliada</TableHead>
            <TableHead>Confiança</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.items.map((receipt) => {
            const meta = RECEIPT_STATUS_META[receipt.status as keyof typeof RECEIPT_STATUS_META];
            const StatusIcon = meta?.icon ?? CheckCircle2;
            return (
              <TableRow
                key={receipt.id}
                className="cursor-pointer"
                onClick={() => onOpen(receipt.id)}
              >
                <TableCell>{date(receipt.purchase_date)}</TableCell>
                <TableCell>{receipt.merchant_name ?? EM_DASH}</TableCell>
                <TableCell
                  className="max-w-[12rem] truncate"
                  title={receipt.parser_profile_name ?? undefined}
                >
                  {receipt.parser_profile_name ?? EM_DASH}
                </TableCell>
                <TableCell className="numeric">{eur(receipt.total_eur)}</TableCell>
                <TableCell className="numeric">{eur(receipt.fs_value_eur)}</TableCell>
                <TableCell className="numeric">{eur(receipt.notional_total_eur)}</TableCell>
                <TableCell
                  className="numeric"
                  title={`${receipt.printed_item_count} impressos + ${receipt.fs_item_count} Fs`}
                >
                  {receipt.printed_item_count}/{receipt.fs_item_count}
                </TableCell>
                <TableCell>
                  <Badge variant={meta?.variant ?? 'muted'}>
                    <StatusIcon />
                    {meta?.label ?? receipt.status}
                  </Badge>
                </TableCell>
                <TableCell>
                  {receipt.is_reconciled ? (
                    <span className="flex items-center gap-1.5 text-success">
                      <CheckCircle2 className="size-4" />
                      reconciliada
                    </span>
                  ) : (
                    <span className="flex items-center gap-1.5 text-destructive">
                      <XCircle className="size-4" />
                      por reconciliar
                    </span>
                  )}
                </TableCell>
                <TableCell className="numeric">
                  {percent(receipt.confidence ? Number(receipt.confidence) * 100 : null)}
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
