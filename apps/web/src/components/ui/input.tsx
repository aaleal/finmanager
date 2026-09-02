import * as React from 'react';
import * as LabelPrimitive from '@radix-ui/react-label';
import { CalendarDays, Eye, EyeOff } from 'lucide-react';
import { cn } from '@/lib/utils';

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type, ...props }, ref) => (
    <input
      type={type}
      ref={ref}
      className={cn(
        'flex h-9 w-full rounded-lg border border-input bg-card px-3 py-1 text-sm shadow-soft transition-colors',
        'placeholder:text-placeholder file:border-0 file:bg-transparent file:text-sm file:font-medium',
        'disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = 'Input';

/** A password field with a right-hand icon that toggles it in and out of view. */
export const PasswordInput = React.forwardRef<
  HTMLInputElement,
  Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type'>
>(({ className, ...props }, ref) => {
  const [visible, setVisible] = React.useState(false);
  return (
    <div className="relative">
      <Input ref={ref} type={visible ? 'text' : 'password'} className={cn('pr-9', className)} {...props} />
      <button
        type="button"
        tabIndex={-1}
        onClick={() => setVisible((value) => !value)}
        aria-label={visible ? 'Esconder palavra-passe' : 'Mostrar palavra-passe'}
        className="absolute inset-y-0 right-0 flex w-9 items-center justify-center text-muted-foreground transition-colors hover:text-foreground"
      >
        {visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
      </button>
    </div>
  );
});
PasswordInput.displayName = 'PasswordInput';

/**
 * A date typed the Portuguese way — `dd/mm/aaaa` — over an ISO value.
 *
 * The native `type="date"` renders in the *browser's* locale, so an English
 * Chrome shows `mm/dd/yyyy` on a pt-PT screen and there is no attribute that
 * changes it. The text field is therefore ours; the native input survives behind
 * the calendar icon, so the picker still works.
 */
export function DateInput({
  value,
  onChange,
  className,
  disabled,
  'aria-label': ariaLabel,
}: {
  value: string | null | undefined;
  onChange: (isoDate: string) => void;
  className?: string;
  disabled?: boolean;
  'aria-label'?: string;
}) {
  const iso = value ?? '';
  const [draft, setDraft] = React.useState(() => isoToPt(iso));

  React.useEffect(() => {
    setDraft((current) => (ptToIso(current) === iso ? current : isoToPt(iso)));
  }, [iso]);

  return (
    <div className={cn('relative', className)}>
      <Input
        value={draft}
        disabled={disabled}
        aria-label={ariaLabel}
        inputMode="numeric"
        maxLength={10}
        placeholder="dd/mm/aaaa"
        className="pr-9"
        onChange={(event) => {
          const masked = maskPtDate(event.target.value);
          setDraft(masked);
          const parsed = ptToIso(masked);
          if (parsed !== null) onChange(parsed);
        }}
      />
      <CalendarDays className="pointer-events-none absolute right-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
      <input
        type="date"
        tabIndex={-1}
        aria-hidden
        disabled={disabled}
        value={iso}
        onChange={(event) => onChange(event.target.value)}
        onClick={(event) => event.currentTarget.showPicker?.()}
        className="absolute inset-y-0 right-0 w-9 cursor-pointer opacity-0"
      />
    </div>
  );
}

function isoToPt(iso: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  return match ? `${match[3]}/${match[2]}/${match[1]}` : '';
}

/** `''` for an empty field, `null` while the date is still half-typed. */
function ptToIso(text: string): string | null {
  if (!text.trim()) return '';
  const match = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(text);
  if (!match) return null;
  const [, day, month, year] = match;
  const date = new Date(`${year}-${month}-${day}T00:00:00`);
  if (date.getUTCDate() !== Number(day) && date.getDate() !== Number(day)) return null;
  return `${year}-${month}-${day}`;
}

function maskPtDate(text: string): string {
  const digits = text.replace(/\D/g, '').slice(0, 8);
  const parts = [digits.slice(0, 2), digits.slice(2, 4), digits.slice(4, 8)].filter(Boolean);
  return parts.join('/');
}

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      'flex min-h-[72px] w-full rounded-lg border border-input bg-card px-3 py-2 text-sm shadow-soft',
      'placeholder:text-placeholder disabled:cursor-not-allowed disabled:opacity-50',
      className,
    )}
    {...props}
  />
));
Textarea.displayName = 'Textarea';

export const Label = React.forwardRef<
  React.ElementRef<typeof LabelPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof LabelPrimitive.Root>
>(({ className, ...props }, ref) => (
  <LabelPrimitive.Root
    ref={ref}
    className={cn(
      'text-sm font-medium leading-none text-foreground peer-disabled:cursor-not-allowed peer-disabled:opacity-70',
      className,
    )}
    {...props}
  />
));
Label.displayName = 'Label';

export function Field({
  label,
  hint,
  error,
  htmlFor,
  className,
  children,
}: {
  label?: React.ReactNode;
  hint?: React.ReactNode;
  error?: React.ReactNode;
  htmlFor?: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={cn('space-y-1.5', className)}>
      {label ? <Label htmlFor={htmlFor}>{label}</Label> : null}
      {children}
      {error ? (
        <p className="text-xs font-medium text-destructive">{error}</p>
      ) : hint ? (
        <p className="text-xs text-muted-foreground">{hint}</p>
      ) : null}
    </div>
  );
}
