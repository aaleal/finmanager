import * as React from 'react';
import { Search } from 'lucide-react';
import type { CategoryResult } from '@/lib/types';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/primitives';
import { useDebounced } from '@/lib/filters';
import { cn } from '@/lib/utils';
import { useCategorySearch } from './catalogue-api';

/**
 * Search-as-you-type category combobox.
 *
 * Always renders the full `L1 › L2 › L3` path, never just the leaf name — the
 * same leaf name under two parents would otherwise be ambiguous.
 */
export function CategoryPicker({
  value,
  onSelect,
  disabled,
  allowClear,
  placeholder = 'Procurar categoria…',
}: {
  value?: string | null;
  onSelect: (category: CategoryResult | null) => void;
  disabled?: boolean;
  allowClear?: boolean;
  placeholder?: string;
}) {
  const [open, setOpen] = React.useState(false);
  const [query, setQuery] = React.useState('');
  const debouncedQuery = useDebounced(query, 300);
  const search = useCategorySearch(debouncedQuery);
  const results = search.data ?? [];

  function choose(category: CategoryResult | null) {
    onSelect(category);
    setOpen(false);
    setQuery('');
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          disabled={disabled}
          className={cn(
            'flex h-9 w-full items-center gap-2 rounded-lg border border-input bg-card px-3 py-1 text-left text-sm shadow-soft transition-colors',
            'disabled:cursor-not-allowed disabled:opacity-50',
          )}
        >
          <Search className="size-4 shrink-0 text-muted-foreground" />
          <span className={cn('truncate', !value && 'text-placeholder')}>{value ?? placeholder}</span>
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-96 space-y-2 p-2" align="start">
        <Input
          autoFocus
          placeholder="Nome da categoria…"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <div className="max-h-72 overflow-y-auto">
          {allowClear ? (
            <button
              type="button"
              onClick={() => choose(null)}
              className="mb-0.5 flex w-full items-center rounded-md px-2 py-1.5 text-left text-sm text-muted-foreground hover:bg-muted"
            >
              Sem categoria
            </button>
          ) : null}
          {search.isFetching && debouncedQuery.trim().length >= 2 ? (
            <p className="px-2 py-3 text-sm text-muted-foreground">A procurar…</p>
          ) : results.length ? (
            <ul className="space-y-0.5">
              {results.map((category) => (
                <li key={category.id}>
                  <button
                    type="button"
                    onClick={() => choose(category)}
                    className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left hover:bg-muted"
                  >
                    <Badge variant="outline" className="shrink-0">
                      N{category.level}
                    </Badge>
                    <span className="truncate text-sm">{category.path}</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="px-2 py-3 text-sm text-muted-foreground">Sem categorias correspondentes.</p>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
