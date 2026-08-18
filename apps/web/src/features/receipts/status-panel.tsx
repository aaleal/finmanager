import * as React from 'react';
import { AlertTriangle, Inbox, ListChecks, Merge, Percent, ScanLine, Tags } from 'lucide-react';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/feedback';
import { Tooltip } from '@/components/ui/primitives';
import { num, percent } from '@/lib/format';
import { cn } from '@/lib/utils';
import { useReceiptStatusBoard } from './api';

function StatusCard({
  icon: Icon,
  label,
  value,
  hint,
  onClick,
  disabledHint,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: React.ReactNode;
  hint?: React.ReactNode;
  onClick?: () => void;
  disabledHint?: string;
}) {
  const body = (
    <Card
      className={cn(
        'text-left transition',
        onClick && 'cursor-pointer hover:-translate-y-0.5 hover:shadow-card',
        disabledHint && 'opacity-60',
      )}
    >
      <CardHeader className="flex-row items-center gap-2 space-y-0 pb-1 text-muted-foreground">
        <Icon className="size-4" />
        <span className="text-xs font-medium uppercase tracking-wide">{label}</span>
      </CardHeader>
      <CardContent className="pt-0">
        <p className="numeric text-2xl font-semibold tracking-tight">{value}</p>
        {hint ? <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p> : null}
      </CardContent>
    </Card>
  );

  if (disabledHint) {
    return (
      <Tooltip label={disabledHint}>
        <div>{body}</div>
      </Tooltip>
    );
  }

  if (onClick) {
    return (
      <button type="button" onClick={onClick} className="w-full">
        {body}
      </button>
    );
  }

  return body;
}

export function ReceiptStatusPanel({
  onNavigate,
}: {
  onNavigate: (tab: string, patch?: Record<string, string>) => void;
}) {
  const board = useReceiptStatusBoard();

  if (board.isLoading || !board.data) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, index) => (
          <Skeleton key={index} className="h-28 rounded-xl" />
        ))}
      </div>
    );
  }

  const data = board.data;

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <StatusCard
        icon={Inbox}
        label="Faturas por processar"
        value={num(data.to_process)}
        hint={data.failed_jobs > 0 ? `${data.failed_jobs} falhadas` : undefined}
        onClick={() => onNavigate('processamento')}
      />
      <StatusCard
        icon={ScanLine}
        label="Faturas por validar"
        value={num(data.to_validate)}
        onClick={() => onNavigate('faturas', { status: 'NEEDS_REVIEW' })}
      />
      <StatusCard
        icon={ListChecks}
        label="Linhas por resolver"
        value={num(data.unresolved_lines)}
        onClick={() => onNavigate('artigos')}
      />
      <StatusCard
        icon={Tags}
        label="Produtos por categorizar"
        value={num(data.uncategorized_products)}
        onClick={() => onNavigate('produtos', { category_status: 'AUTO' })}
      />
      <StatusCard
        icon={Merge}
        label="Produtos a fundir"
        value={num(data.merge_candidates)}
        onClick={() => onNavigate('produtos')}
      />
      <StatusCard
        icon={Percent}
        label="Taxa de auto-aceitação observada"
        value={percent(
          data.observed_auto_accept_rate !== null ? data.observed_auto_accept_rate * 100 : null,
        )}
        hint={
          <>
            <span className="flex items-center gap-1">
              <AlertTriangle className="size-3" />
              observada sobre
            </span>
            <span>{num(data.decided_receipts)} faturas decididas</span>
          </>
        }
      />
    </div>
  );
}
