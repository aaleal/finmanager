import * as React from 'react';
import { Check, ChevronRight, MapPin } from 'lucide-react';
import type { StorageLocation } from '@/lib/types';
import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/primitives';
import { cn } from '@/lib/utils';

export interface StorageSelection {
  storage_location_id?: string;
  storage_area?: string;
}

/**
 * Two-level storage picker.
 *
 * The table is flat (`area` + `container`) and stays that way; only this control
 * is hierarchical. Areas start collapsed so the list opens as «Casa · Garagem ·
 * Sala» rather than as every shelf at once, and picking an area alone means
 * "everything in it" (FR-9.16).
 */
export function StorageFilter({
  locations,
  value,
  onChange,
}: {
  locations: StorageLocation[];
  value: StorageSelection;
  onChange: (selection: StorageSelection) => void;
}) {
  const [open, setOpen] = React.useState(false);
  const [expanded, setExpanded] = React.useState<string[]>([]);

  const areas = React.useMemo(() => {
    const map = new Map<string, StorageLocation[]>();
    for (const location of locations) {
      const list = map.get(location.area) ?? [];
      // An area row with no container is the area itself, not a child of it.
      if (location.container) list.push(location);
      map.set(location.area, list);
    }
    return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0], 'pt-PT'));
  }, [locations]);

  const selected = locations.find((location) => location.id === value.storage_location_id);
  const label = selected
    ? selected.label
    : value.storage_area
      ? `Toda a área «${value.storage_area}»`
      : 'Qualquer local';

  // Reopening the picker should show where the current filter lives.
  React.useEffect(() => {
    const area = selected?.area ?? value.storage_area;
    if (open && area)
      setExpanded((previous) => (previous.includes(area) ? previous : [...previous, area]));
  }, [open, selected?.area, value.storage_area]);

  function toggle(area: string) {
    setExpanded((previous) =>
      previous.includes(area) ? previous.filter((name) => name !== area) : [...previous, area],
    );
  }

  function choose(selection: StorageSelection) {
    onChange(selection);
    setOpen(false);
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          className="w-full justify-start font-normal"
          aria-label="Filtrar por arrumação"
        >
          <MapPin className="text-muted-foreground" />
          <span className="truncate">{label}</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-80 p-1.5">
        <div className="max-h-80 overflow-y-auto">
          <Row
            label="Qualquer local"
            selected={!value.storage_location_id && !value.storage_area}
            onClick={() => choose({})}
          />

          {areas.map(([area, containers]) => {
            const isOpen = expanded.includes(area);
            return (
              <div key={area}>
                <div className="flex items-center gap-0.5">
                  {containers.length ? (
                    <button
                      type="button"
                      onClick={() => toggle(area)}
                      aria-label={isOpen ? `Fechar ${area}` : `Abrir ${area}`}
                      aria-expanded={isOpen}
                      className="rounded p-1 text-muted-foreground hover:bg-muted"
                    >
                      <ChevronRight
                        className={cn('size-4 transition-transform', isOpen && 'rotate-90')}
                      />
                    </button>
                  ) : (
                    <span className="size-6" aria-hidden />
                  )}
                  <Row
                    className="flex-1"
                    label={area}
                    hint={containers.length ? `${containers.length} locais` : undefined}
                    selected={value.storage_area === area}
                    onClick={() => choose({ storage_area: area })}
                  />
                </div>

                {isOpen
                  ? containers.map((location) => (
                      <Row
                        key={location.id}
                        className="ml-7"
                        label={location.container ?? area}
                        hint={location.is_full ? 'cheio' : undefined}
                        selected={value.storage_location_id === location.id}
                        onClick={() => choose({ storage_location_id: location.id })}
                      />
                    ))
                  : null}
              </div>
            );
          })}
        </div>
      </PopoverContent>
    </Popover>
  );
}

function Row({
  label,
  hint,
  selected,
  onClick,
  className,
}: {
  label: string;
  hint?: string;
  selected: boolean;
  onClick: () => void;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted',
        selected && 'bg-muted font-medium',
        className,
      )}
    >
      <span className="truncate">{label}</span>
      {hint ? <span className="shrink-0 text-xs text-muted-foreground">{hint}</span> : null}
      {selected ? <Check className="ml-auto size-4 shrink-0 text-primary" /> : null}
    </button>
  );
}
