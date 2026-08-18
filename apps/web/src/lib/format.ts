/**
 * The single money/date/number formatting surface.
 *
 * EUR is comma-decimal pt-PT (`1 234,56 €`) and amounts arrive from the API as
 * decimal strings — they are never parsed into a float for display. Thousands are
 * always separated by a non-breaking space, including four-digit amounts, which
 * pt-PT leaves ungrouped by default (`minimumGroupingDigits: 2`).
 */

/** Non-breaking, so `1 234,56 €` never wraps mid-number. */
const GROUP_SEPARATOR = '\u00a0';

const EUR = new Intl.NumberFormat('pt-PT', {
  style: 'currency',
  currency: 'EUR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
  useGrouping: 'always',
});

const EUR_COMPACT = new Intl.NumberFormat('pt-PT', {
  style: 'currency',
  currency: 'EUR',
  notation: 'compact',
  maximumFractionDigits: 1,
});

const NUMBER = new Intl.NumberFormat('pt-PT', { useGrouping: 'always' });

const WEIGHT = new Intl.NumberFormat('pt-PT', {
  minimumFractionDigits: 3,
  maximumFractionDigits: 3,
  useGrouping: 'always',
});

/** Force the group separator regardless of the ICU data the runtime ships with. */
function spaced(formatter: Intl.NumberFormat, value: number): string {
  return formatter
    .formatToParts(value)
    .map((part) => (part.type === 'group' ? GROUP_SEPARATOR : part.value))
    .join('');
}

const DATE = new Intl.DateTimeFormat('pt-PT', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
});

const DATE_LONG = new Intl.DateTimeFormat('pt-PT', {
  day: 'numeric',
  month: 'long',
  year: 'numeric',
});

const DATETIME = new Intl.DateTimeFormat('pt-PT', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
});

export type Money = string | number | null | undefined;

export const EM_DASH = '—';

export function eur(value: Money, fallback = EM_DASH): string {
  if (value === null || value === undefined || value === '') return fallback;
  const numeric = typeof value === 'string' ? Number(value) : value;
  if (Number.isNaN(numeric)) return fallback;
  return spaced(EUR, numeric);
}

export function eurCompact(value: Money, fallback = EM_DASH): string {
  if (value === null || value === undefined || value === '') return fallback;
  const numeric = typeof value === 'string' ? Number(value) : value;
  if (Number.isNaN(numeric)) return fallback;
  return EUR_COMPACT.format(numeric);
}

/** ROI is `null` for gifts and for sets with no value — never faked as 0 %. */
export function percent(value: Money, fallback = EM_DASH): string {
  if (value === null || value === undefined || value === '') return fallback;
  const numeric = typeof value === 'string' ? Number(value) : value;
  if (Number.isNaN(numeric)) return fallback;
  const sign = numeric > 0 ? '+' : '';
  return `${sign}${spaced(NUMBER, Math.round(numeric * 10) / 10)} %`;
}

export function signedEur(value: Money, fallback = EM_DASH): string {
  if (value === null || value === undefined || value === '') return fallback;
  const numeric = typeof value === 'string' ? Number(value) : value;
  if (Number.isNaN(numeric)) return fallback;
  return `${numeric > 0 ? '+' : ''}${spaced(EUR, numeric)}`;
}

export function num(value: number | null | undefined, fallback = EM_DASH): string {
  if (value === null || value === undefined) return fallback;
  return spaced(NUMBER, value);
}

/**
 * Weights are always three decimals — a receipt scale prints `0,302 kg`, and
 * rounding it to two would silently move the €/kg it divides into.
 */
export function weightKg(value: Money, fallback = EM_DASH): string {
  if (value === null || value === undefined || value === '') return fallback;
  const numeric = typeof value === 'string' ? Number(value) : value;
  if (Number.isNaN(numeric)) return fallback;
  return `${spaced(WEIGHT, numeric)} kg`;
}

/**
 * Quantity is a count, so it renders as an integer. A product priced at the
 * counter has no meaningful count at all — the weight is the relevant field —
 * so it renders as a dash rather than a fabricated `1`.
 */
export function quantity(
  value: Money,
  { soldByWeight = false }: { soldByWeight?: boolean } = {},
): string {
  if (soldByWeight) return EM_DASH;
  if (value === null || value === undefined || value === '') return EM_DASH;
  const numeric = typeof value === 'string' ? Number(value) : value;
  if (Number.isNaN(numeric)) return EM_DASH;
  return spaced(NUMBER, Math.round(numeric));
}

export function date(value: string | Date | null | undefined, fallback = EM_DASH): string {
  if (!value) return fallback;
  const parsed = typeof value === 'string' ? new Date(value) : value;
  if (Number.isNaN(parsed.getTime())) return fallback;
  return DATE.format(parsed);
}

export function dateLong(value: string | Date | null | undefined, fallback = EM_DASH): string {
  if (!value) return fallback;
  const parsed = typeof value === 'string' ? new Date(value) : value;
  if (Number.isNaN(parsed.getTime())) return fallback;
  return DATE_LONG.format(parsed);
}

export function dateTime(value: string | Date | null | undefined, fallback = EM_DASH): string {
  if (!value) return fallback;
  const parsed = typeof value === 'string' ? new Date(value) : value;
  if (Number.isNaN(parsed.getTime())) return fallback;
  return DATETIME.format(parsed);
}

export function relativeDays(value: string | null | undefined): string {
  if (!value) return 'nunca';
  const days = Math.floor((Date.now() - new Date(value).getTime()) / 86_400_000);
  if (days <= 0) return 'hoje';
  if (days === 1) return 'ontem';
  if (days < 30) return `há ${days} dias`;
  if (days < 365) return `há ${Math.round(days / 30)} meses`;
  const years = Math.round(days / 365);
  return years === 1 ? 'há 1 ano' : `há ${years} anos`;
}

export function toDateInput(value: string | null | undefined): string {
  if (!value) return '';
  return value.slice(0, 10);
}
