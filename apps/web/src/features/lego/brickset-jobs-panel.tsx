import * as React from 'react';
import { Ban, RotateCw } from 'lucide-react';
import type { LegoBricksetJob } from '@/lib/types';
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
import { dateTime } from '@/lib/format';
import { useBricksetJobs, useCancelBricksetJob, useRetryBricksetJob } from './api';

const JOB_TYPE_LABELS: Record<string, string> = {
  lego_brickset_images: 'Imagens',
  lego_brickset_manuals: 'Manuais',
};

const STATUS_BADGE: Record<
  string,
  { label: string; variant: 'muted' | 'warning' | 'success' | 'destructive' | 'outline' }
> = {
  QUEUED: { label: 'Em fila', variant: 'muted' },
  RUNNING: { label: 'Em curso', variant: 'warning' },
  SUCCEEDED: { label: 'Concluído', variant: 'success' },
  FAILED: { label: 'Falhou', variant: 'destructive' },
  CANCELLED: { label: 'Cancelado', variant: 'outline' },
};

const ACTIVE_STATUSES = new Set(['QUEUED', 'RUNNING']);
const RETRYABLE_STATUSES = new Set(['FAILED', 'CANCELLED']);

/**
 * Visibility into the background images/manuals fetch (ADR-0049) — one row per
 * job, grouped implicitly by set via the set name/number shown on every row.
 * Polls only while something is still queued/running (see `useBricksetJobs`).
 * Rendered as its own tab section on the LEGO page (not a dialog).
 */
export function BricksetJobsSection() {
  const jobs = useBricksetJobs();
  const cancel = useCancelBricksetJob();
  const retry = useRetryBricksetJob();
  const [pendingId, setPendingId] = React.useState<string | null>(null);

  async function handleCancel(id: string) {
    setPendingId(id);
    try {
      await cancel.mutateAsync(id);
    } finally {
      setPendingId(null);
    }
  }

  async function handleRetry(id: string) {
    setPendingId(id);
    try {
      await retry.mutateAsync(id);
    } finally {
      setPendingId(null);
    }
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        As fotografias extra e os manuais de cada conjunto novo são obtidos em segundo plano — esta
        lista mostra o que está em fila, em curso, ou por resolver.
      </p>

      {jobs.data && jobs.data.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">
          Sem processos em curso ou recentes.
        </p>
      ) : (
        <div className="max-h-[60vh] overflow-y-auto rounded-lg border border-border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Conjunto</TableHead>
                <TableHead>Tipo</TableHead>
                <TableHead>Estado</TableHead>
                <TableHead>Atualizado</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {(jobs.data ?? []).map((job) => (
                <BricksetJobRow
                  key={job.id}
                  job={job}
                  busy={pendingId === job.id}
                  onCancel={() => handleCancel(job.id)}
                  onRetry={() => handleRetry(job.id)}
                />
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

function BricksetJobRow({
  job,
  busy,
  onCancel,
  onRetry,
}: {
  job: LegoBricksetJob;
  busy: boolean;
  onCancel: () => void;
  onRetry: () => void;
}) {
  const status = STATUS_BADGE[job.status] ?? { label: job.status, variant: 'muted' as const };
  const updated = job.completed_at ?? job.started_at ?? job.created_at;
  return (
    <TableRow>
      <TableCell>
        <div className="flex flex-col">
          <span className="font-medium">{job.set_name}</span>
          {job.set_number ? (
            <span className="text-xs text-muted-foreground">{job.set_number}</span>
          ) : null}
        </div>
      </TableCell>
      <TableCell>{JOB_TYPE_LABELS[job.job_type] ?? job.job_type}</TableCell>
      <TableCell>
        <div className="flex flex-col gap-1">
          <Badge variant={status.variant}>{status.label}</Badge>
          {job.status === 'FAILED' && job.last_error ? (
            <span className="max-w-[16rem] text-xs text-destructive">{job.last_error}</span>
          ) : null}
        </div>
      </TableCell>
      <TableCell className="text-xs text-muted-foreground">{dateTime(updated)}</TableCell>
      <TableCell className="text-right">
        {ACTIVE_STATUSES.has(job.status) ? (
          <Button variant="ghost" size="sm" loading={busy} onClick={onCancel}>
            <Ban className="size-3.5" />
            Cancelar
          </Button>
        ) : null}
        {RETRYABLE_STATUSES.has(job.status) ? (
          <Button variant="ghost" size="sm" loading={busy} onClick={onRetry}>
            <RotateCw className="size-3.5" />
            Repetir
          </Button>
        ) : null}
      </TableCell>
    </TableRow>
  );
}
