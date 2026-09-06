import type { AcquisitionSource, BuildState, Condition, OwnershipStatus } from '@/lib/types';

export const BUILD_STATE_LABELS: Record<BuildState, string> = {
  BUILT: 'Montado',
  DISASSEMBLED: 'Desmontado',
};

export const CONDITION_LABELS: Record<Condition, string> = {
  SEALED: 'Selado',
  NEW: 'Novo',
  GOOD: 'Bom',
  WORN: 'Usado',
  DAMAGED: 'Danificado',
};

export const SOURCE_LABELS: Record<AcquisitionSource, string> = {
  CONTINENTE: 'Continente',
  AMAZON: 'Amazon',
  OTHER_STORE: 'Outra loja',
  SECONDHAND: 'Em segunda mão',
  GIFT: 'Prenda',
  OTHER: 'Outro',
};

export const OWNERSHIP_LABELS: Record<OwnershipStatus, string> = {
  IN_COLLECTION: 'Na coleção',
  SOLD: 'Vendido',
  GIFTED: 'Oferecido',
};

export const CONDITION_VARIANTS: Record<
  Condition,
  'success' | 'secondary' | 'warning' | 'destructive'
> = {
  SEALED: 'success',
  NEW: 'success',
  GOOD: 'secondary',
  WORN: 'warning',
  DAMAGED: 'destructive',
};

/**
 * Condition is an ordinal quality scale, so colour carries meaning there.
 * Build state is a neutral fact — sealed is not "better" than built — so it stays
 * on a single neutral tint (M9.1). The label always says what the colour means.
 */
export const BUILD_STATE_VARIANT = 'outline' as const;

/**
 * Every column the grid renders is sortable, plus the two things it does not show.
 * The `column` key is what the header uses; the select lists all of them.
 */
export const SORT_FIELDS = [
  { value: 'created', label: 'Adicionado' },
  { value: 'number', label: 'Número' },
  { value: 'name', label: 'Nome' },
  { value: 'theme', label: 'Tema' },
  { value: 'copies', label: 'Cópias' },
  { value: 'pieces', label: 'Peças' },
  { value: 'minifigs', label: 'Minifiguras' },
  { value: 'year', label: 'Lançamento' },
  { value: 'retired', label: 'Retirada' },
  { value: 'storage', label: 'Arrumação' },
  { value: 'state', label: 'Estado' },
  { value: 'condition', label: 'Condição' },
  { value: 'acquired', label: 'Data de aquisição' },
  { value: 'cost', label: 'Custo' },
  { value: 'rrp', label: 'PVP' },
  { value: 'value', label: 'Valor' },
  { value: 'roi', label: 'ROI' },
  { value: 'ownership', label: 'Propriedade' },
];

export const COMPLETENESS_OPTIONS = [
  { value: 'all', label: 'Completos e incompletos' },
  { value: 'complete', label: 'Só completos' },
  { value: 'incomplete', label: 'Só incompletos' },
];

export const RETIREMENT_OPTIONS = [
  { value: 'all', label: 'Retirados e à venda' },
  { value: 'retired', label: 'Só retirados' },
  { value: 'available', label: 'Só ainda à venda' },
];

export const COPIES_OPTIONS = [
  { value: 'all', label: 'Uma ou mais cópias' },
  { value: 'multiple', label: 'Só com cópias repetidas' },
  { value: 'single', label: 'Só com uma cópia' },
];

export const FS_OPTIONS = [
  { value: 'all', label: 'Fs e não Fs' },
  { value: 'fs', label: 'Só Fs' },
  { value: 'not_fs', label: 'Só não Fs' },
];

export const PAGE_SIZES = ['10', '25', '50', '100', '200'];

/**
 * External marketplace links are built from `set_number` on the client and never
 * stored, fetched or refreshed (M9 FR-9.10).
 */
export function externalLinks(setNumber: string) {
  const bare = setNumber.replace(/-\d+$/, '');
  return [
    { label: 'Brickset', href: `https://brickset.com/sets/${bare}-1` },
    {
      label: 'BrickLink',
      href: `https://www.bricklink.com/v2/catalog/catalogitem.page?S=${bare}-1`,
    },
    { label: 'BrickEconomy', href: `https://www.brickeconomy.com/set/${bare}-1` },
    { label: 'Rebrickable', href: `https://rebrickable.com/sets/${bare}-1/` },
  ];
}

/** `18+` when the box has no upper age, `6-12` when it does. */
export function ageRangeLabel(
  min: number | null | undefined,
  max: number | null | undefined,
): string | null {
  if (min == null && max == null) return null;
  if (min != null && max != null) return min === max ? `${min}` : `${min}–${max}`;
  return min != null ? `${min}+` : `até ${max}`;
}

/** The box prints one age, so the form asks for one: `18+`, `+4` or `6-12`. */
export function ageRangeInput(
  min: number | null | undefined,
  max: number | null | undefined,
): string {
  return ageRangeLabel(min, max) ?? '';
}

export function parseAgeRange(text: string): { min: number | null; max: number | null } {
  const trimmed = text.trim();
  const range = /^(\d{1,3})\s*[-–]\s*(\d{1,3})$/.exec(trimmed);
  if (range) return { min: Number(range[1]), max: Number(range[2]) };
  const single = /^\+?(\d{1,3})\+?$/.exec(trimmed);
  return single ? { min: Number(single[1]), max: null } : { min: null, max: null };
}

/** The box as it is printed on the back: comprimento × largura × altura. */
export function boxDimensionsLabel(
  width: string | null | undefined,
  depth: string | null | undefined,
  height: string | null | undefined,
): string | null {
  const parts = [width, depth, height];
  if (parts.every((part) => !part)) return null;
  return `${parts.map((part) => (part ? Number(part).toLocaleString('pt-PT') : '?')).join(' × ')} cm`;
}

/** The same three sides in one editable field, without the unit. */
export function boxDimensionsInput(
  width: string | null | undefined,
  depth: string | null | undefined,
  height: string | null | undefined,
): string {
  const parts = [width, depth, height];
  if (parts.every((part) => !part)) return '';
  return parts.map((part) => (part ? Number(part).toLocaleString('pt-PT') : '')).join(' × ');
}

export function parseBoxDimensions(text: string): {
  width: string | null;
  depth: string | null;
  height: string | null;
} {
  const [width, depth, height] = text.split(/[x×*]/i).map((part) => part.trim().replace(',', '.'));
  const side = (part: string | undefined) => {
    const parsed = Number(part);
    return part && Number.isFinite(parsed) && parsed >= 0 ? parsed.toFixed(1) : null;
  };
  return { width: side(width), depth: side(depth), height: side(height) };
}

/** The two languages this household reads; anything else is never imported. */
export const INSTRUCTION_LANGUAGE_LABELS: Record<string, string> = {
  EN: 'Inglês',
  ENGB: 'Inglês (GB)',
  ENUS: 'Inglês (US)',
  PT: 'Português',
  PTBR: 'Português (BR)',
};
