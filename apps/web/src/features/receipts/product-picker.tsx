import * as React from 'react';
import { Plus, Search } from 'lucide-react';
import type { ProductSearchResult } from '@/lib/types';
import { Input } from '@/components/ui/input';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/primitives';
import { useDebounced } from '@/lib/filters';
import { percent } from '@/lib/format';
import { cn } from '@/lib/utils';
import { useProductSearch } from './catalogue-api';

/**
 * Search-as-you-type product combobox.
 *
 * Seeding the input from the merchant's own wording (`merchantDescription`) is the
 * whole point: it means a near-duplicate product is never created by hand just
 * because the picker started empty.
 */
export function ProductPicker({
  value,
  merchantDescription,
  onSelect,
  onCreate,
  placeholder = 'Procurar produto…',
  disabled,
}: {
  value?: string | null;
  merchantDescription?: string;
  onSelect: (product: ProductSearchResult) => void;
  onCreate?: (name: string) => void;
  placeholder?: string;
  disabled?: boolean;
}) {
  const [open, setOpen] = React.useState(false);
  const [query, setQuery] = React.useState('');
  const debouncedQuery = useDebounced(query, 300);
  const search = useProductSearch(debouncedQuery);
  const results = search.data ?? [];

  React.useEffect(() => {
    if (open && !query && merchantDescription) setQuery(merchantDescription);
  }, [open, query, merchantDescription]);

  function choose(product: ProductSearchResult) {
    onSelect(product);
    setOpen(false);
    setQuery('');
  }

  function createNew() {
    const name = query.trim();
    if (!onCreate || !name) return;
    onCreate(name);
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
            'flex w-full items-center gap-2 rounded-lg border border-input bg-card px-3 py-1.5 text-left text-[length:inherit] shadow-soft transition-colors',
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
          placeholder="Nome, marca ou alias…"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <div className="max-h-72 overflow-y-auto">
          {search.isFetching && debouncedQuery.trim().length >= 2 ? (
            <p className="px-2 py-3 text-sm text-muted-foreground">A procurar…</p>
          ) : results.length ? (
            <ul className="space-y-0.5">
              {results.map((product) => (
                <li key={product.id}>
                  <button
                    type="button"
                    onClick={() => choose(product)}
                    className="flex w-full flex-col gap-0.5 rounded-md px-2 py-1.5 text-left hover:bg-muted"
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span className="truncate font-medium">{product.canonical_name}</span>
                      <span className="numeric shrink-0 text-xs text-muted-foreground">
                        {percent(product.score * 100)}
                      </span>
                    </span>
                    <span className="truncate text-xs text-muted-foreground">
                      {product.brand ?? '—'} · {product.category_path ?? '—'}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="px-2 py-3 text-sm text-muted-foreground">Sem produtos correspondentes.</p>
          )}
        </div>
        {onCreate ? (
          <button
            type="button"
            disabled={!query.trim()}
            onClick={createNew}
            className="flex w-full items-center gap-2 rounded-md border-t border-border px-2 pt-2 text-left text-sm text-primary hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Plus className="size-4" />
            Criar novo produto “{query.trim()}”
          </button>
        ) : null}
      </PopoverContent>
    </Popover>
  );
}
