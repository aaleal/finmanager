import * as React from 'react';
import { Check, ChevronsUpDown, Users } from 'lucide-react';
import { useSession } from '@/features/auth/session';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';

/**
 * Global entity selector (M7 FR-7.2). Entity is an attribution filter — every
 * household member still reads everything, so this never hides data for
 * permission reasons, only narrows the view.
 */
export function EntitySelector() {
  const { entities, activeEntity, setActiveEntity } = useSession();
  const [pending, setPending] = React.useState(false);

  async function select(entityId: string | null) {
    setPending(true);
    try {
      await setActiveEntity(entityId);
    } finally {
      setPending(false);
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          className="h-9 min-w-[11rem] justify-between gap-2 px-3"
          loading={pending}
        >
          <span className="flex min-w-0 items-center gap-2">
            <span
              className="size-2.5 shrink-0 rounded-full"
              style={{ backgroundColor: activeEntity?.color ?? '#94a3b8' }}
              aria-hidden
            />
            <span className="truncate text-sm font-medium">{activeEntity?.name ?? 'Todas'}</span>
          </span>
          <ChevronsUpDown className="size-3.5 shrink-0 opacity-50" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-60">
        <DropdownMenuLabel>Ver como</DropdownMenuLabel>
        <DropdownMenuItem onSelect={() => select(null)}>
          <Users className="text-muted-foreground" />
          <span className="flex-1">Todas as entidades</span>
          {!activeEntity ? <Check className="size-4 text-primary" /> : null}
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        {entities.map((entity) => (
          <DropdownMenuItem key={entity.id} onSelect={() => select(entity.id)}>
            <span
              className="size-2.5 rounded-full"
              style={{ backgroundColor: entity.color ?? '#94a3b8' }}
              aria-hidden
            />
            <span className={cn('flex-1 truncate', entity.is_readonly && 'text-muted-foreground')}>
              {entity.name}
            </span>
            {entity.is_readonly ? (
              <span className="text-[10px] uppercase text-muted-foreground">leitura</span>
            ) : null}
            {activeEntity?.id === entity.id ? <Check className="size-4 text-primary" /> : null}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
