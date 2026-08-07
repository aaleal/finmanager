import * as React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Landmark, Link2, Search } from 'lucide-react';
import { api } from '@/lib/api';
import type { SuggestionResponse, TransactionSuggestion } from '@/lib/types';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { EmptyState } from '@/components/ui/feedback';
import { date, eur } from '@/lib/format';

/**
 * Shared transaction picker (specified in M9 UX-9.7, owned by the shared layer).
 *
 * Proposes bank transactions near a date with a similar amount, ranked, with free
 * search as a fallback. Reused by M1/M3/M4/M5 once those modules land; until the
 * ledger exists (M2) the endpoint answers `ledger_available: false` and the
 * component says so instead of pretending to search.
 */
export function TransactionPicker({
  open,
  onOpenChange,
  nearDate,
  amountEur,
  onSelect,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  nearDate?: string | null;
  amountEur?: string | null;
  onSelect: (transaction: TransactionSuggestion) => void;
}) {
  const [search, setSearch] = React.useState('');

  const suggestions = useQuery({
    queryKey: ['transactions', 'suggest', nearDate, amountEur, search],
    queryFn: () =>
      api.get<SuggestionResponse>('/transactions/suggest', {
        near_date: nearDate ?? undefined,
        amount_eur: amountEur ?? undefined,
        search: search || undefined,
      }),
    enabled: open,
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="md">
        <DialogHeader>
          <DialogTitle>Ligar ao extrato bancário</DialogTitle>
          <DialogDescription>
            Movimentos próximos de {date(nearDate)} com valor semelhante a {eur(amountEur)}.
          </DialogDescription>
        </DialogHeader>

        <DialogBody className="space-y-4">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              className="pl-9"
              placeholder="Procurar por descrição…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              disabled={!suggestions.data?.ledger_available}
            />
          </div>

          {!suggestions.data?.ledger_available ? (
            <EmptyState
              icon={Landmark}
              title="Livro-razão ainda não disponível"
              description={
                suggestions.data?.message ??
                'O módulo de Banca chega numa fase seguinte. Pode registar a compra sem ligação ao extrato.'
              }
            />
          ) : suggestions.data.items.length === 0 ? (
            <EmptyState
              icon={Link2}
              title="Sem movimentos correspondentes"
              description="Alargue a pesquisa ou registe a compra sem ligação."
            />
          ) : (
            <ul className="divide-y divide-border rounded-lg border border-border">
              {suggestions.data.items.map((transaction) => (
                <li key={transaction.id}>
                  <button
                    type="button"
                    onClick={() => {
                      onSelect(transaction);
                      onOpenChange(false);
                    }}
                    className="flex w-full items-center justify-between gap-4 px-4 py-3 text-left transition hover:bg-muted/60"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">{transaction.description}</p>
                      <p className="text-xs text-muted-foreground">
                        {date(transaction.booked_date)} · {transaction.account_label ?? 'Conta'}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-3">
                      <Badge variant="secondary">{Math.round(transaction.score * 100)} %</Badge>
                      <span className="numeric text-sm font-semibold">
                        {eur(transaction.amount_eur)}
                      </span>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </DialogBody>

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Fechar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
