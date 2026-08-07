import * as React from 'react';
import { useSearchParams } from 'react-router-dom';

/**
 * Filter state lives in the URL so every view is bookmarkable and shareable, and
 * so it can be fed straight into a TanStack Query key.
 */
export function useUrlFilters<T extends Record<string, string | undefined>>(defaults: T) {
  const [searchParams, setSearchParams] = useSearchParams();

  const values = React.useMemo(() => {
    const result = { ...defaults };
    for (const key of Object.keys(defaults) as (keyof T)[]) {
      const fromUrl = searchParams.get(String(key));
      if (fromUrl !== null) result[key] = fromUrl as T[keyof T];
    }
    return result;
  }, [searchParams, defaults]);

  const setValues = React.useCallback(
    (patch: Partial<Record<keyof T, string | undefined>>, options?: { resetPage?: boolean }) => {
      setSearchParams(
        (previous) => {
          const next = new URLSearchParams(previous);
          for (const [key, value] of Object.entries(patch)) {
            if (value === undefined || value === '' || value === defaults[key as keyof T]) {
              next.delete(key);
            } else {
              next.set(key, String(value));
            }
          }
          if (options?.resetPage !== false && !('page' in patch)) next.delete('page');
          return next;
        },
        { replace: true },
      );
    },
    [setSearchParams, defaults],
  );

  const reset = React.useCallback(() => {
    setSearchParams(new URLSearchParams(), { replace: true });
  }, [setSearchParams]);

  return [values, setValues, reset] as const;
}

export function useDebounced<T>(value: T, delay = 300) {
  const [debounced, setDebounced] = React.useState(value);
  React.useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}
