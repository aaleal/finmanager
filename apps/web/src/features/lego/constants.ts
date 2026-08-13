import type { AcquisitionSource, BuildState, Condition, OwnershipStatus } from '@/lib/types';

export const BUILD_STATE_LABELS: Record<BuildState, string> = {
  SEALED: 'Selado',
  BUILT: 'Montado',
  DISASSEMBLED: 'Desmontado',
};

export const CONDITION_LABELS: Record<Condition, string> = {
  NEW: 'Novo',
  GOOD: 'Bom',
  WORN: 'Usado',
  DAMAGED: 'Danificado',
};

export const SOURCE_LABELS: Record<AcquisitionSource, string> = {
  RETAIL: 'Loja',
  SECONDHAND: 'Em segunda mão',
  GIFT: 'Prenda',
  OTHER: 'Outro',
};

export const OWNERSHIP_LABELS: Record<OwnershipStatus, string> = {
  IN_COLLECTION: 'Na coleção',
  SOLD: 'Vendido',
  GIFTED: 'Oferecido',
};

export const CONDITION_VARIANTS: Record<Condition, 'success' | 'secondary' | 'warning' | 'destructive'> = {
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

export const SORT_FIELDS = [
  { value: 'created', label: 'Adicionado' },
  { value: 'name', label: 'Nome' },
  { value: 'pieces', label: 'Peças' },
  { value: 'year', label: 'Ano' },
  { value: 'cost', label: 'Custo' },
  { value: 'value', label: 'Valor' },
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

/**
 * External marketplace links are built from `set_number` on the client and never
 * stored, fetched or refreshed (M9 FR-9.10).
 */
export function externalLinks(setNumber: string) {
  const bare = setNumber.replace(/-\d+$/, '');
  return [
    { label: 'Brickset', href: `https://brickset.com/sets/${bare}-1` },
    { label: 'BrickLink', href: `https://www.bricklink.com/v2/catalog/catalogitem.page?S=${bare}-1` },
    { label: 'BrickEconomy', href: `https://www.brickeconomy.com/set/${bare}-1` },
    { label: 'Rebrickable', href: `https://rebrickable.com/sets/${bare}-1/` },
  ];
}
