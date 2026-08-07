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

export const SORT_OPTIONS = [
  { value: 'created_desc', label: 'Adicionado (recente)' },
  { value: 'created_asc', label: 'Adicionado (antigo)' },
  { value: 'name_asc', label: 'Nome (A–Z)' },
  { value: 'name_desc', label: 'Nome (Z–A)' },
  { value: 'value_desc', label: 'Valor atual (maior)' },
  { value: 'value_asc', label: 'Valor atual (menor)' },
  { value: 'cost_desc', label: 'Custo (maior)' },
  { value: 'cost_asc', label: 'Custo (menor)' },
  { value: 'pieces_desc', label: 'Peças (mais)' },
  { value: 'year_desc', label: 'Ano (recente)' },
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
