import { HelpCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/primitives';
import { percent } from '@/lib/format';

interface Reason {
  rule?: unknown;
  detail?: unknown;
  score?: unknown;
}

function isReason(value: unknown): value is Reason {
  return typeof value === 'object' && value !== null;
}

export function WhyPopover({ reasons, label = 'Porquê?' }: { reasons: unknown[]; label?: string }) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="sm">
          <HelpCircle />
          {label}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="space-y-2">
        {reasons.length ? (
          <ul className="space-y-2">
            {reasons.map((raw, index) => {
              const reason = isReason(raw) ? raw : {};
              const score =
                typeof reason.score === 'string' && reason.score !== ''
                  ? Number(reason.score)
                  : typeof reason.score === 'number'
                    ? reason.score
                    : null;
              return (
                <li key={index} className="flex items-start justify-between gap-3 text-sm">
                  <div className="min-w-0">
                    <p className="font-mono text-xs text-muted-foreground">
                      {typeof reason.rule === 'string' ? reason.rule : '—'}
                    </p>
                    <p>{typeof reason.detail === 'string' ? reason.detail : String(reason.detail ?? '')}</p>
                  </div>
                  {score !== null && !Number.isNaN(score) ? (
                    <span className="numeric shrink-0 text-right text-xs text-muted-foreground">
                      {percent(score * 100)}
                    </span>
                  ) : null}
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">Sem razões registadas.</p>
        )}
      </PopoverContent>
    </Popover>
  );
}
