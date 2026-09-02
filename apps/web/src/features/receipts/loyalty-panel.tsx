import * as React from 'react';
import { CreditCard, ExternalLink, Info } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { EmptyState, Skeleton } from '@/components/ui/feedback';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { EM_DASH, date, eur } from '@/lib/format';
import { cn } from '@/lib/utils';
import { useLoyalty, useLoyaltyReceipts } from './prices-api';

export function LoyaltyPanel({ onOpenReceipt }: { onOpenReceipt: (receiptId: string) => void }) {
  const loyalty = useLoyalty();
  const [selected, setSelected] = React.useState<{
    scheme: string;
    cardMasked: string | null;
  } | null>(null);

  const receipts = useLoyaltyReceipts(selected?.scheme ?? null, selected?.cardMasked ?? null);
  const groups = loyalty.data ?? [];

  if (loyalty.isLoading) {
    return <Skeleton className="h-64 rounded-xl" />;
  }

  if (!groups.length) {
    return <EmptyState icon={CreditCard} title="Nenhuma fatura com cartão de fidelização." />;
  }

  return (
    <div className="space-y-4">
      <p className="flex items-start gap-1.5 text-xs text-muted-foreground">
        <Info className="size-3.5 shrink-0 translate-y-0.5" />O desconto do cartão é repartido
        proporcionalmente pelas linhas a que se aplicou — nunca somado aos descontos de artigo.
      </p>

      <Card>
        <CardHeader>
          <CardTitle>Cartões de fidelização</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Esquema</TableHead>
                <TableHead>Cartão</TableHead>
                <TableHead>Faturas</TableHead>
                <TableHead>Acumulado</TableHead>
                <TableHead>Utilizado</TableHead>
                <TableHead>Primeiro uso</TableHead>
                <TableHead>Último uso</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {groups.map((group, index) => {
                const isSelected =
                  Boolean(group.scheme) &&
                  selected?.scheme === group.scheme &&
                  selected?.cardMasked === group.card_masked;
                return (
                  <TableRow
                    key={`${group.scheme ?? 'sem-esquema'}-${group.card_masked ?? 'sem-cartao'}-${index}`}
                    className={cn(group.scheme && 'cursor-pointer', isSelected && 'bg-secondary')}
                    onClick={() =>
                      group.scheme &&
                      setSelected({ scheme: group.scheme, cardMasked: group.card_masked })
                    }
                  >
                    <TableCell className="font-medium">{group.scheme ?? EM_DASH}</TableCell>
                    <TableCell>{group.card_masked ?? EM_DASH}</TableCell>
                    <TableCell className="numeric">{group.receipt_count}</TableCell>
                    <TableCell className="numeric">{eur(group.accrued_eur)}</TableCell>
                    <TableCell className="numeric">{eur(group.discount_eur)}</TableCell>
                    <TableCell>{date(group.first_purchase)}</TableCell>
                    <TableCell>{date(group.last_purchase)}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {selected ? (
        <Card>
          <CardHeader>
            <CardTitle>
              Faturas — {selected.scheme} {selected.cardMasked ?? ''}
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            {receipts.isLoading ? (
              <Skeleton className="h-40 rounded-lg" />
            ) : (receipts.data ?? []).length === 0 ? (
              <EmptyState icon={CreditCard} title="Sem faturas para este cartão." />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Data</TableHead>
                    <TableHead>Comerciante</TableHead>
                    <TableHead>Total</TableHead>
                    <TableHead>Desconto do cartão</TableHead>
                    <TableHead>Acumulado</TableHead>
                    <TableHead>Repartido pelas linhas</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(receipts.data ?? []).map((allocation) => (
                    <TableRow key={allocation.receipt_id}>
                      <TableCell>{date(allocation.purchase_date)}</TableCell>
                      <TableCell>{allocation.merchant_name ?? EM_DASH}</TableCell>
                      <TableCell className="numeric">{eur(allocation.total_eur)}</TableCell>
                      <TableCell className="numeric">
                        {eur(allocation.loyalty_discount_eur)}
                      </TableCell>
                      <TableCell className="numeric">
                        {eur(allocation.loyalty_accrued_eur)}
                      </TableCell>
                      <TableCell className="numeric">
                        {eur(allocation.allocated_across_items_eur)}
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => onOpenReceipt(allocation.receipt_id)}
                        >
                          <ExternalLink />
                          Abrir
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
