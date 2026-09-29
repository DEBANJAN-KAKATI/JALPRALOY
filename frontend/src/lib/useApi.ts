import { useEffect, useState, type DependencyList } from "react";

export interface ApiState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
}

const RETRY_DELAYS_MS = [5_000, 15_000]; // flaky networks are normal during floods

/** Fetch on mount and whenever deps change. Keeps the previous data while
 * refreshing, so cards don't flash empty every 5 minutes, and retries a failed
 * request twice (5 s, 15 s) before giving up until the next refresh. Pass `null` to skip. */
export function useApi<T>(fn: (() => Promise<T>) | null, deps: DependencyList): ApiState<T> {
  const [state, setState] = useState<ApiState<T>>({ data: null, error: null, loading: !!fn });

  useEffect(() => {
    if (!fn) {
      setState({ data: null, error: null, loading: false });
      return;
    }
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const attempt = (n: number) => {
      fn()
        .then((data) => !cancelled && setState({ data, error: null, loading: false }))
        .catch((e: Error) => {
          if (cancelled) return;
          if (n < RETRY_DELAYS_MS.length) {
            timer = setTimeout(() => attempt(n + 1), RETRY_DELAYS_MS[n]);
          } else {
            setState((s) => ({ data: s.data, error: e.message, loading: false }));
          }
        });
    };
    setState((s) => ({ ...s, loading: true }));
    attempt(0);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return state;
}
