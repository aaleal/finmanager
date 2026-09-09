import * as React from 'react';
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

/**
 * The «Porquê?» affordance: every auto-filled value can show the reasons and
 * scores behind it.
 *
 * `trigger` replaces the icon when the caller has something better to click — the
 * confidence itself, for instance, which says more than a question mark and
 * costs the same space.
 */
export function WhyPopover({
  reasons,
  label = 'Porquê?',
  title,
  confidence = null,
  formula,
  trigger,
}: {
  reasons: unknown[];
  label?: string | null;
  title?: string;
  confidence?: number | null;
  formula?: string;
  trigger?: React.ReactNode;
}) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        {trigger ?? (
          <Button
            variant="ghost"
            size={label === null ? 'icon-sm' : 'sm'}
            title={title ?? 'Porquê?'}
            aria-label={title ?? 'Porquê?'}
          >
            <HelpCircle />
            {label}
          </Button>
        )}
      </PopoverTrigger>
      <PopoverContent className="w-96 space-y-2">
        {confidence !== null ? (
          <div className="flex items-baseline justify-between border-b border-border pb-2">
            <span className="text-sm font-medium">Confiança final</span>
            <span className="numeric text-lg font-semibold">{percent(confidence)}</span>
          </div>
        ) : null}
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
                    <p>
                      {typeof reason.detail === 'string'
                        ? reason.detail
                        : String(reason.detail ?? '')}
                    </p>
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
        {formula ? (
          <p className="border-t border-border pt-2 text-xs text-muted-foreground">
            <span className="font-medium">Cálculo:</span> {formula}
          </p>
        ) : null}
      </PopoverContent>
    </Popover>
  );
}
