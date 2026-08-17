import * as React from 'react';
import { Info, Link2, Unlink } from 'lucide-react';
import { TransactionPicker } from '@/components/transaction-picker';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/feedback';
import { useSession } from '@/features/auth/session';
import { EM_DASH, percent } from '@/lib/format';
import type { TransactionSuggestion } from '@/lib/types';
import { useLinkReceipt, useReceiptLink, useUnlinkReceipt } from './prices-api';
import { WhyPopover } from './why-popover';

export function ReceiptLinkPanel({
  receiptId,
  purchaseDate,
  totalEur,
}: {
  receiptId: string;
  purchaseDate: string | null;
  totalEur: string;
}) {
  const { canWrite } = useSession();
  const link = useReceiptLink(receiptId);
  const linkReceipt = useLinkReceipt();
  const unlinkReceipt = useUnlinkReceipt();
  const [pickerOpen, setPickerOpen] = React.useState(false);

  if (link.isLoading || !link.data) {
    return <Skeleton className="h-20 rounded-xl" />;
  }

  const data = link.data;

  if (!data.ledger_available) {
    return (
      <div className="flex items-start gap-2 rounded-lg border border-border bg-muted/40 px-3 py-2.5 text-sm text-muted-foreground">
        <Info className="size-4 shrink-0 translate-y-0.5" />
        <p>{data.message ?? 'Ligação ao extrato bancário ainda não disponível.'}</p>
      </div>
    );
  }

  const confidencePct = data.confidence !== null && data.confidence !== undefined
    ? Number(data.confidence) * 100
    : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Ligação ao extrato bancário</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 pt-0">
        {data.link_id ? (
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <Badge variant="outline">{data.status ?? EM_DASH}</Badge>
              <span className="numeric text-muted-foreground">
                Confiança: {percent(confidencePct)}
              </span>
              <WhyPopover reasons={data.decision_reasons ?? []} />
            </div>
            {canWrite ? (
              <Button
                variant="outline"
                size="sm"
                loading={unlinkReceipt.isPending}
                onClick={() => unlinkReceipt.mutate(receiptId)}
              >
                <Unlink />
                Desligar
              </Button>
            ) : null}
          </div>
        ) : canWrite ? (
          <Button variant="outline" size="sm" onClick={() => setPickerOpen(true)}>
            <Link2 />
            Ligar a movimento bancário
          </Button>
        ) : (
          <p className="text-sm text-muted-foreground">Sem ligação ao extrato bancário.</p>
        )}
      </CardContent>

      <TransactionPicker
        open={pickerOpen}
        onOpenChange={setPickerOpen}
        nearDate={purchaseDate}
        amountEur={totalEur}
        onSelect={(transaction: TransactionSuggestion) =>
          linkReceipt.mutate({ receiptId, transactionId: transaction.id })
        }
      />
    </Card>
  );
}
