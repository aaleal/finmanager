import * as React from 'react';
import { Check, Snowflake, Tag, Utensils } from 'lucide-react';
import type { AttributeOption } from '@/lib/types';
import { Badge } from '@/components/ui/badge';
import { Field } from '@/components/ui/input';
import {
  Checkbox,
  Popover,
  PopoverContent,
  PopoverTrigger,
  Switch,
} from '@/components/ui/primitives';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';
import { useProductAttributes } from './catalogue-api';

/** `Select` cannot hold an empty string, and "por indicar" is a real answer here
 * — a product nobody has annotated yet is not an error (ADR-0059). */
export const UNSET = '__unset__';

export type ProductAttributes = {
  is_own_brand: boolean;
  conservation: string | null;
  presentation: string | null;
  dietary_attributes: string[];
};

export function emptyAttributes(): ProductAttributes {
  return { is_own_brand: false, conservation: null, presentation: null, dietary_attributes: [] };
}

function labelOf(options: AttributeOption[] | undefined, value: string | null): string | null {
  if (!value) return null;
  return options?.find((option) => option.value === value)?.label ?? value;
}

/** Read-only chips for the tables, so a row shows what it can now be filtered by. */
export function AttributeBadges({
  isOwnBrand,
  conservation,
  presentation,
  dietary,
  className,
}: {
  isOwnBrand?: boolean;
  conservation?: string | null;
  presentation?: string | null;
  dietary?: string[] | null;
  className?: string;
}) {
  const vocabulary = useProductAttributes();
  const chips: React.ReactNode[] = [];
  if (isOwnBrand) {
    chips.push(
      <Badge key="own" variant="muted">
        marca branca
      </Badge>,
    );
  }
  const conservationLabel = labelOf(vocabulary.data?.conservation, conservation ?? null);
  if (conservationLabel) {
    chips.push(
      <Badge key="cons" variant="outline">
        <Snowflake />
        {conservationLabel}
      </Badge>,
    );
  }
  if (presentation) {
    chips.push(
      <Badge key="pres" variant="outline">
        <Utensils />
        {presentation}
      </Badge>,
    );
  }
  for (const tag of dietary ?? []) {
    chips.push(
      <Badge key={`diet-${tag}`} variant="success">
        {tag}
      </Badge>,
    );
  }
  if (!chips.length) return null;
  return <span className={cn('flex flex-wrap items-center gap-1', className)}>{chips}</span>;
}

/** Multi-select: tags are transversal, so a product carries as many as apply. */
export function DietaryPicker({
  value,
  options,
  onChange,
  disabled,
}: {
  value: string[];
  options: AttributeOption[];
  onChange: (value: string[]) => void;
  disabled?: boolean;
}) {
  const [open, setOpen] = React.useState(false);

  function toggle(tag: string) {
    onChange(value.includes(tag) ? value.filter((item) => item !== tag) : [...value, tag]);
  }

  return (
    <Popover open={open} onOpenChange={setOpen} modal>
      <PopoverTrigger asChild>
        <button
          type="button"
          disabled={disabled}
          className={cn(
            'flex min-h-9 w-full flex-wrap items-center gap-1 rounded-lg border border-input bg-card px-3 py-1.5 text-left text-sm shadow-soft transition-colors',
            'disabled:cursor-not-allowed disabled:opacity-50',
          )}
        >
          {value.length ? (
            value.map((tag) => (
              <Badge key={tag} variant="success">
                {tag}
              </Badge>
            ))
          ) : (
            <span className="text-placeholder">Sem atributos dietéticos</span>
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-72 p-2" align="start">
        <ul className="max-h-72 space-y-0.5 overflow-y-auto">
          {options.map((option) => (
            <li key={option.value}>
              <button
                type="button"
                onClick={() => toggle(option.value)}
                className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted"
              >
                <Checkbox checked={value.includes(option.value)} tabIndex={-1} />
                <span className="flex-1 truncate">{option.label}</span>
                {value.includes(option.value) ? <Check className="size-3.5 text-primary" /> : null}
              </button>
            </li>
          ))}
        </ul>
      </PopoverContent>
    </Popover>
  );
}

/** The four Fase 1/2 attributes as one block, shared by the create dialog and the
 * product sheet so the two can never offer different vocabularies. */
export function ProductAttributeFields({
  value,
  onChange,
  disabled,
}: {
  value: ProductAttributes;
  onChange: (value: ProductAttributes) => void;
  disabled?: boolean;
}) {
  const vocabulary = useProductAttributes();
  const conservation = vocabulary.data?.conservation ?? [];
  const presentation = vocabulary.data?.presentation ?? [];
  const dietary = vocabulary.data?.dietary ?? [];

  const patch = (changes: Partial<ProductAttributes>) => onChange({ ...value, ...changes });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between rounded-lg border border-border px-3 py-2">
        <div className="flex items-center gap-2 text-sm">
          <Tag className="size-4 text-muted-foreground" />
          Marca branca
        </div>
        <Switch
          checked={value.is_own_brand}
          onCheckedChange={(checked) => patch({ is_own_brand: checked })}
          disabled={disabled}
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Conservação">
          <Select
            value={value.conservation ?? UNSET}
            disabled={disabled}
            onValueChange={(next) => patch({ conservation: next === UNSET ? null : next })}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={UNSET}>Por indicar</SelectItem>
              {conservation.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
        <Field label="Corte / apresentação">
          <Select
            value={value.presentation ?? UNSET}
            disabled={disabled}
            onValueChange={(next) => patch({ presentation: next === UNSET ? null : next })}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={UNSET}>Por indicar</SelectItem>
              {presentation.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
      </div>

      <Field
        label="Atributos dietéticos"
        hint="Atravessam as categorias — nunca fazem parte da identidade do produto."
      >
        <DietaryPicker
          value={value.dietary_attributes}
          options={dietary}
          disabled={disabled}
          onChange={(tags) => patch({ dietary_attributes: tags })}
        />
      </Field>
    </div>
  );
}
