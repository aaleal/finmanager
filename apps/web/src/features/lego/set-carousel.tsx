import * as React from 'react';
import { Blocks, ChevronLeft, ChevronRight, Images } from 'lucide-react';
import type { LegoSetModel } from '@/lib/types';
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog';
import { cn } from '@/lib/utils';

export interface Frame {
  key: string;
  url: string;
  caption: string | null;
  /** The underlying `Document` id, so a per-copy pick can be matched back to a frame. */
  documentId: string | null;
  /** Whether this is the set's current box shot (ADR-0045: a flag, not a position). */
  isCover: boolean;
}
/**
 * A copy photograph, when there is one, leads — it is *this* box, not the
 * catalog's. The cover otherwise gets its own leading frame, unless it is
 * already one of the gallery's own images (promoted there without moving),
 * in which case it is only shown once, at its own place in the gallery.
 */
export function frames(model: LegoSetModel | null, photoUrl?: string | null): Frame[] {
  const list: Frame[] = [];
  if (photoUrl) {
    list.push({
      key: 'photo',
      url: photoUrl,
      caption: 'Fotografia desta cópia',
      documentId: null,
      isCover: false,
    });
  }
  const coverDocumentId = model?.image_document_id ?? null;
  const coverInGallery =
    coverDocumentId !== null &&
    (model?.images ?? []).some((image) => image.document_id === coverDocumentId);
  if (model?.image_url && !coverInGallery) {
    list.push({
      key: 'cover',
      url: model.image_url,
      caption: 'Caixa',
      documentId: coverDocumentId,
      isCover: true,
    });
  }
  for (const image of model?.images ?? []) {
    if (image.url) {
      list.push({
        key: image.id,
        url: image.url,
        caption: image.caption ?? null,
        documentId: image.document_id,
        isCover: image.document_id === coverDocumentId,
      });
    }
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

/** How many `size-N` tiles (N × 4px, Tailwind's spacing scale) fit per row at
 * the container's current width — recomputed on resize, not a fixed breakpoint. */
export function useTilesPerRow(tileSizeClass: string, gapPx = 6) {
  const tilePx = Number(tileSizeClass.replace('size-', '')) * 4;
  // State (not a plain ref) so the container mounting *after* the initial
  // render — e.g. behind a collapsed section — still triggers measurement.
  const [el, setEl] = React.useState<HTMLDivElement | null>(null);
  const [perRow, setPerRow] = React.useState(4);

  React.useEffect(() => {
    if (!el) return;
    const measure = () =>
      setPerRow(Math.max(1, Math.floor((el.clientWidth + gapPx) / (tilePx + gapPx))));
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, [el, tilePx, gapPx]);

  return { ref: setEl, perRow };
}

/** A "+N" tile that reveals the rest of a row-capped strip or grid on click. */
export function OverflowTile({
  count,
  size,
  title,
  onClick,
}: {
  count: number;
  size: string;
  title: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      className={cn(
        size,
        'flex shrink-0 flex-col items-center justify-center gap-0.5 rounded border border-dashed border-border bg-muted text-muted-foreground hover:bg-muted/70',
      )}
    >
      <Images className="size-4" />
      <span className="text-xs font-medium">+{count}</span>
    </button>
  );
}

/** The lightbox's thumbnail row: a single line, scrolled horizontally — a mouse
 * wheel's usual vertical gesture is redirected sideways, since the strip itself
 * never grows tall enough to need vertical scrolling. */
function ThumbStrip({
  items,
  index,
  onSelect,
  size = 'size-16',
}: {
  items: Frame[];
  index: number;
  onSelect: (position: number) => void;
  size?: string;
}) {
  return (
    <div
      className="flex gap-1.5 overflow-x-auto pb-1"
      onWheel={(event) => {
        if (event.deltaY === 0) return;
        event.currentTarget.scrollLeft += event.deltaY;
        event.preventDefault();
      }}
    >
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

/**
 * Just the stage, its arrows, and the lightbox it opens into on click — no
 * inline thumbnail row (that lives, when one is wanted, wherever the caller
 * puts it, e.g. `GalleryEditor`). The frame shown by default is the copy's own
 * photograph if there is one, otherwise the set's current cover.
 */
export function SetCarousel({ items, className }: { items: Frame[]; className?: string }) {
  const leadIndex = React.useMemo(() => {
    if (items[0]?.key === 'photo') return 0;
    const coverIndex = items.findIndex((item) => item.isCover);
    return coverIndex === -1 ? 0 : coverIndex;
  }, [items]);

  const [index, setIndex] = React.useState(leadIndex);
  const [lightboxOpen, setLightboxOpen] = React.useState(false);

  // Jump to the lead frame whenever it changes — a promotion elsewhere, or the
  // gallery shrinking under the frame currently shown.
  React.useEffect(() => setIndex(leadIndex), [leadIndex]);

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
  const step = (delta: number) => setIndex((index + delta + items.length) % items.length);

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
          {items.length > 1 ? <ThumbStrip items={items} index={index} onSelect={setIndex} /> : null}
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
