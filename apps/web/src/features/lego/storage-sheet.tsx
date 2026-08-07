import * as React from 'react';
import { toast } from 'sonner';
import { Boxes, Plus, Trash2 } from 'lucide-react';
import type { StorageLocation } from '@/lib/types';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Field, Input } from '@/components/ui/input';
import { Separator, Slider } from '@/components/ui/primitives';
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  SheetContent,
} from '@/components/ui/dialog';
import { EmptyState } from '@/components/ui/feedback';
import { eur, num } from '@/lib/format';
import { cn } from '@/lib/utils';
import { useSession } from '@/features/auth/session';
import { useStorageMutations } from './api';

const PRESETS = [0, 25, 50, 75, 100];

function CapacityControl({ location }: { location: StorageLocation }) {
  const { update } = useStorageMutations();
  const [value, setValue] = React.useState(location.capacity_pct ?? 0);
  const [tracked, setTracked] = React.useState(location.capacity_pct !== null);

  React.useEffect(() => {
    setValue(location.capacity_pct ?? 0);
    setTracked(location.capacity_pct !== null);
  }, [location.capacity_pct]);

  function commit(next: number | null) {
    update.mutate({ id: location.id, capacity_pct: next });
  }

  if (!tracked) {
    return (
      <Button
        variant="outline"
        size="sm"
        onClick={() => {
          setTracked(true);
          commit(50);
        }}
      >
        Estimar ocupação
      </Button>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-3">
        <Slider
          value={[value]}
          min={0}
          max={100}
          step={5}
          onValueChange={([next]) => setValue(next)}
          onValueCommit={([next]) => commit(next)}
          className="flex-1"
        />
        <span className="numeric w-12 shrink-0 text-right text-sm font-medium">{value} %</span>
      </div>
      <div className="flex flex-wrap items-center gap-1">
        {PRESETS.map((preset) => (
          <Button
            key={preset}
            size="sm"
            variant={value === preset ? 'secondary' : 'ghost'}
            className="h-7 px-2 text-xs"
            onClick={() => {
              setValue(preset);
              commit(preset);
            }}
          >
            {preset} %
          </Button>
        ))}
        <Button
          size="sm"
          variant="ghost"
          className="h-7 px-2 text-xs text-muted-foreground"
          onClick={() => {
            setTracked(false);
            commit(null);
          }}
        >
          não seguir
        </Button>
      </div>
    </div>
  );
}

function AddLocationDialog() {
  const [open, setOpen] = React.useState(false);
  const [area, setArea] = React.useState('');
  const [container, setContainer] = React.useState('');
  const [description, setDescription] = React.useState('');
  const { create } = useStorageMutations();

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <Button size="sm" variant="outline" onClick={() => setOpen(true)}>
        <Plus />
        Novo local
      </Button>
      <DialogContent size="sm">
        <DialogHeader>
          <DialogTitle>Novo local de arrumação</DialogTitle>
          <DialogDescription>
            Uma lista plana de área + contentor, mostrada como «Garagem › Caixa TV».
          </DialogDescription>
        </DialogHeader>
        <DialogBody className="space-y-4">
          <Field label="Área">
            <Input
              placeholder="Garagem"
              value={area}
              onChange={(event) => setArea(event.target.value)}
            />
          </Field>
          <Field label="Contentor" hint="Caixa, prateleira ou estado (por exemplo, «Montado»).">
            <Input
              placeholder="Caixa TV"
              value={container}
              onChange={(event) => setContainer(event.target.value)}
            />
          </Field>
          <Field label="Descrição">
            <Input value={description} onChange={(event) => setDescription(event.target.value)} />
          </Field>
        </DialogBody>
        <DialogFooter>
          <Button variant="ghost" onClick={() => setOpen(false)}>
            Cancelar
          </Button>
          <Button
            disabled={!area.trim()}
            loading={create.isPending}
            onClick={async () => {
              await create.mutateAsync({
                area: area.trim(),
                container: container.trim() || null,
                description: description.trim() || null,
              });
              setArea('');
              setContainer('');
              setDescription('');
              setOpen(false);
            }}
          >
            Criar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function StorageSheet({
  open,
  onOpenChange,
  locations,
  onShowContents,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  locations: StorageLocation[];
  onShowContents: (locationId: string) => void;
}) {
  const { canWrite } = useSession();
  const { remove } = useStorageMutations();

  const areas = React.useMemo(() => {
    const grouped = new Map<string, StorageLocation[]>();
    for (const location of locations) {
      const list = grouped.get(location.area) ?? [];
      list.push(location);
      grouped.set(location.area, list);
    }
    return [...grouped.entries()];
  }, [locations]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <SheetContent width="md" className="p-0">
        <div className="flex h-full min-h-0 flex-col">
          <div className="shrink-0 space-y-1 border-b border-border px-6 py-4 pr-12">
            <DialogTitle>Arrumação</DialogTitle>
            <DialogDescription>
              A percentagem de ocupação é sempre uma estimativa sua — nunca é calculada a partir do
              número de peças.
            </DialogDescription>
          </div>

          <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-6 py-5">
            {canWrite ? (
              <div className="flex justify-end">
                <AddLocationDialog />
              </div>
            ) : null}

            {areas.length === 0 ? (
              <EmptyState
                icon={Boxes}
                title="Sem locais definidos"
                description="Crie uma área e um contentor para saber onde está cada cópia."
              />
            ) : (
              areas.map(([area, items]) => (
                <div key={area} className="space-y-3">
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    {area}
                  </p>
                  {items.map((location) => (
                    <div key={location.id} className="space-y-3 rounded-lg border border-border p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate font-medium">{location.container ?? area}</p>
                          {location.description ? (
                            <p className="truncate text-xs text-muted-foreground">
                              {location.description}
                            </p>
                          ) : null}
                        </div>
                        <div className="flex shrink-0 items-center gap-1.5">
                          {location.is_full ? (
                            <Badge variant="destructive">cheio</Badge>
                          ) : location.capacity_pct !== null && location.capacity_pct >= 80 ? (
                            <Badge variant="warning">quase cheio</Badge>
                          ) : null}
                          {canWrite ? (
                            <Button
                              variant="ghost"
                              size="icon-sm"
                              className="text-muted-foreground hover:text-destructive"
                              onClick={() =>
                                remove.mutate(location.id, {
                                  onError: () =>
                                    toast.error(
                                      'Mova primeiro as cópias guardadas neste local.',
                                    ),
                                })
                              }
                            >
                              <Trash2 />
                            </Button>
                          ) : null}
                        </div>
                      </div>

                      <div className="flex items-center gap-4 text-sm">
                        <button
                          type="button"
                          onClick={() => {
                            onShowContents(location.id);
                            onOpenChange(false);
                          }}
                          className="font-medium text-primary hover:underline"
                        >
                          {num(location.stored_count)} cópia(s)
                        </button>
                        <span className="numeric text-muted-foreground">
                          {eur(location.stored_value_eur)}
                        </span>
                        {location.remaining_capacity_pct !== null ? (
                          <span className={cn('ml-auto text-xs', location.is_full && 'text-destructive')}>
                            {location.remaining_capacity_pct} % livre
                          </span>
                        ) : (
                          <span className="ml-auto text-xs text-muted-foreground">
                            ocupação não seguida
                          </span>
                        )}
                      </div>

                      {canWrite ? (
                        <>
                          <Separator />
                          <CapacityControl location={location} />
                        </>
                      ) : null}
                    </div>
                  ))}
                </div>
              ))
            )}
          </div>
        </div>
      </SheetContent>
    </Dialog>
  );
}
