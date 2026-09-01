import * as React from 'react';
import { Blocks, ChevronLeft, ChevronRight } from 'lucide-react';
import type { LegoSetModel } from '@/lib/types';
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog';
import { cn } from '@/lib/utils';

export interface Frame {
  key: string;
  url: string;
  caption: string | null;
}
/**
 * The box shot is always frame zero; the gallery follows in its stored order.
 * A copy photograph, when there is one, comes first — it is *this* box, not the
 * catalog's.
 */
export function frames(model: LegoSetModel | null, photoUrl?: string | null): Frame[] {
  const list: Frame[] = [];
  if (photoUrl) list.push({ key: 'photo', url: photoUrl, caption: 'Fotografia desta cópia' });
  if (model?.image_url) list.push({ key: 'cover', url: model.image_url, caption: 'Caixa' });
  for (const image of model?.images ?? []) {
    if (image.url) list.push({ key: image.id, url: image.url, caption: image.caption ?? null });
  }
  return list;
}

/** The image plus its nav arrows and caption/counter overlay — shared by the
 * inline carousel and the large lightbox, at whatever size the container gives it. */
function CarouselStage({
  frame,
  index,
  total,
  onStep,
  onClick,
  clickable,
  rounded = true,
}: {
  frame: Frame;
  index: number;
  total: number;
  onStep: (delta: number) => void;
  onClick?: () => void;
  clickable?: boolean;
  rounded?: boolean;
}) {
  return (
    <div
      className={cn(
        'group relative aspect-[4/3] overflow-hidden border border-border bg-muted',
        rounded && 'rounded-lg',
      )}
    >
      {clickable ? (
        <button
          type="button"
          onClick={onClick}
          className="block size-full cursor-zoom-in"
          aria-label="Ver em tamanho grande"
        >
          <img
            src={frame.url}
            alt={frame.caption ?? ''}
            className="size-full object-contain"
            loading="lazy"
          />
        </button>
      ) : (
        <img
          src={frame.url}
          alt={frame.caption ?? ''}
          className="size-full object-contain"
          loading="lazy"
        />
      )}

      {total > 1 ? (
        <>
          <CarouselButton side="left" onClick={() => onStep(-1)} />
          <CarouselButton side="right" onClick={() => onStep(1)} />
          <div className="pointer-events-none absolute inset-x-0 bottom-0 flex items-center justify-between gap-2 bg-gradient-to-t from-black/55 to-transparent px-3 py-2">
            <span className="truncate text-xs text-white/90">{frame.caption ?? ''}</span>
            <span className="numeric shrink-0 text-xs text-white/70">
              {index + 1}/{total}
            </span>
          </div>
        </>
      ) : null}
    </div>
  );
}

function ThumbStrip({
  items,
  index,
  onSelect,
  size = 'size-12',
}: {
  items: Frame[];
  index: number;
  onSelect: (position: number) => void;
  size?: string;
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item, position) => (
        <button
          key={item.key}
          type="button"
          onClick={() => onSelect(position)}
          aria-label={item.caption ?? `Imagem ${position + 1}`}
          aria-current={position === index}
          className={cn(
            `${size} shrink-0 overflow-hidden rounded border bg-muted transition-opacity`,
            position === index ? 'border-primary' : 'border-border opacity-60 hover:opacity-100',
          )}
        >
          <img src={item.url} alt="" className="size-full object-cover" loading="lazy" />
        </button>
      ))}
    </div>
  );
}

export function SetCarousel({ items, className }: { items: Frame[]; className?: string }) {
  const [index, setIndex] = React.useState(0);
  const [lightboxOpen, setLightboxOpen] = React.useState(false);

  // Deleting or promoting an image reorders the list under us.
  React.useEffect(() => setIndex((current) => Math.min(current, Math.max(0, items.length - 1))), [items.length]);

  if (items.length === 0) {
    return (
      <div
        className={cn(
          'flex aspect-[4/3] items-center justify-center rounded-lg border border-border bg-muted text-muted-foreground',
          className,
        )}
      >
        <Blocks className="size-8" />
      </div>
    );
  }

  const current = items[Math.min(index, items.length - 1)];
  const step = (delta: number) => setIndex((value) => (value + delta + items.length) % items.length);

  return (
    <div className={cn('space-y-2', className)}>
      <CarouselStage
        frame={current}
        index={index}
        total={items.length}
        onStep={step}
        clickable
        onClick={() => setLightboxOpen(true)}
      />

      {items.length > 1 ? <ThumbStrip items={items} index={index} onSelect={setIndex} /> : null}

      <Dialog open={lightboxOpen} onOpenChange={setLightboxOpen}>
        <DialogContent size="lg" className="space-y-3 p-4">
          <DialogTitle className="sr-only">Galeria do conjunto</DialogTitle>
          <CarouselStage
            frame={current}
            index={index}
            total={items.length}
            onStep={step}
            rounded={false}
          />
          {items.length > 1 ? (
            <ThumbStrip items={items} index={index} onSelect={setIndex} size="size-16" />
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function CarouselButton({ side, onClick }: { side: 'left' | 'right'; onClick: () => void }) {
  const Icon = side === 'left' ? ChevronLeft : ChevronRight;
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={side === 'left' ? 'Imagem anterior' : 'Imagem seguinte'}
      className={cn(
        'absolute top-1/2 flex size-8 -translate-y-1/2 items-center justify-center rounded-full bg-black/45 text-white opacity-0 transition-opacity hover:bg-black/65 group-hover:opacity-100 focus-visible:opacity-100',
        side === 'left' ? 'left-2' : 'right-2',
      )}
    >
      <Icon className="size-4" />
    </button>
  );
}
