import { RotateCcw, Search } from 'lucide-react';
import type { QueueEntry, ReceiptStatus } from '@/lib/types';
import { Badge } from '@/components/ui/badge';
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
import { percent } from '@/lib/format';
import { useSession } from '@/features/auth/session';
import { JOB_STATUS_META, RECEIPT_STATUS_META } from './constants';
import { useReceiptQueue, useReparse } from './api';

function JobStatusBadge({ status }: { status: string }) {
  const meta = JOB_STATUS_META[status];
  const Icon = meta?.icon ?? RotateCcw;
  return (
    <Badge variant={meta?.variant ?? 'muted'}>
      <Icon className={status === 'RUNNING' ? 'animate-spin' : undefined} />
      {meta?.label ?? status}
    </Badge>
  );
}

function ReceiptStatusBadge({ status }: { status: string }) {
  const meta = RECEIPT_STATUS_META[status as ReceiptStatus];
  if (!meta) return <Badge variant="muted">{status}</Badge>;
  const Icon = meta.icon;
  return (
    <Badge variant={meta.variant}>
      <Icon />
      {meta.label}
    </Badge>
  );
}

/**
 * The **processing** queue (UX-1.1): one row per `ProcessingJob`, with the
 * parser profile that ran and retry from the stored document.
 *
 * This is not a review queue and must never become one — everything a human has
 * to decide lives in the single shared Review Queue (`components/review-queue`).
 */
export function ReceiptQueueTable({
  onOpen,
  compact = false,
}: {
  onOpen?: (receiptId: string) => void;
  compact?: boolean;
}) {
  const queue = useReceiptQueue();
  const reparse = useReparse();
  const { canWrite } = useSession();

  if (queue.isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: compact ? 2 : 4 }).map((_, index) => (
          <Skeleton key={index} className="h-12 rounded-lg" />
        ))}
      </div>
    );
  }

  if (!queue.data?.length) {
    return <EmptyState title="Nada em processamento." />;
  }

  const entries = compact ? queue.data.slice(0, 10) : queue.data;

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Ficheiro</TableHead>
          <TableHead>Comerciante</TableHead>
          <TableHead>Algoritmo</TableHead>
          <TableHead>Estado</TableHead>
          {compact ? null : <TableHead>Tentativas</TableHead>}
          <TableHead>Confiança</TableHead>
          <TableHead>Motivo da falha</TableHead>
          <TableHead className="w-20">Ações</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {entries.map((entry: QueueEntry) => {
          const receiptId = entry.receipt_id;
          return (
            <TableRow
              key={entry.processing_job_id}
              className={receiptId && onOpen ? 'cursor-pointer' : undefined}
              onClick={() => receiptId && onOpen?.(receiptId)}
            >
              <TableCell className="max-w-[14rem] truncate" title={entry.filename ?? undefined}>
                {entry.filename ?? '—'}
              </TableCell>
              <TableCell>{entry.merchant_name ?? '—'}</TableCell>
              <TableCell>{entry.parser_profile_name ?? '—'}</TableCell>
              <TableCell>
                <div className="flex flex-wrap items-center gap-1.5">
                  <JobStatusBadge status={entry.job_status} />
                  <ReceiptStatusBadge status={entry.status} />
                </div>
              </TableCell>
              {compact ? null : (
                <TableCell className="numeric">
                  {entry.attempts}/{entry.max_attempts}
                </TableCell>
              )}
              <TableCell className="numeric">
                {percent(entry.confidence !== null ? Number(entry.confidence) * 100 : null)}
              </TableCell>
              <TableCell
                className="max-w-[16rem] truncate text-muted-foreground"
                title={entry.last_error ?? undefined}
              >
                {entry.last_error ?? '—'}
              </TableCell>
              <TableCell>
                {/* Icon-only: the row itself opens the review, so these two are
                    shortcuts and the labels were the widest thing in the table. */}
                <div className="flex items-center gap-1">
                  {canWrite ? (
                    <Button
                      size="icon-sm"
                      variant="ghost"
                      title="Reprocessar a partir do documento guardado — nunca pede um novo carregamento."
                      aria-label="Reprocessar"
                      loading={reparse.isPending}
                      disabled={!receiptId}
                      onClick={(event) => {
                        event.stopPropagation();
                        if (receiptId) reparse.mutate({ receiptId });
                      }}
                    >
                      <RotateCcw />
                    </Button>
                  ) : null}
                  {receiptId && onOpen ? (
                    <Button
                      size="icon-sm"
                      variant="ghost"
                      title="Rever a fatura"
                      aria-label="Rever"
                      onClick={(event) => {
                        event.stopPropagation();
                        onOpen(receiptId);
                      }}
                    >
                      <Search />
                    </Button>
                  ) : null}
                </div>
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
