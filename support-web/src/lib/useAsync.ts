import { useCallback, useEffect, useRef, useState } from 'react';

export type AsyncStatus = 'idle' | 'loading' | 'success' | 'error';

export interface AsyncState<T> {
  status: AsyncStatus;
  data: T | null;
  error: unknown;
}

export interface AsyncHandle<T> extends AsyncState<T> {
  run: (task: () => Promise<T>) => Promise<T | null>;
  reset: () => void;
  setData: (data: T) => void;
}

/**
 * One request's worth of state, with stale responses discarded.
 *
 * The sequence counter is not decoration: someone searching for their warranty
 * on a slow connection will hit the button twice, and without it the first
 * (slower) response can land after the second and overwrite a correct result
 * with an outdated one.
 */
export function useAsync<T>(): AsyncHandle<T> {
  const [state, setState] = useState<AsyncState<T>>({ status: 'idle', data: null, error: null });
  const seq = useRef(0);
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  const run = useCallback(async (task: () => Promise<T>): Promise<T | null> => {
    const ticket = ++seq.current;
    setState({ status: 'loading', data: null, error: null });
    try {
      const data = await task();
      if (!alive.current || ticket !== seq.current) return null;
      setState({ status: 'success', data, error: null });
      return data;
    } catch (error) {
      if (!alive.current || ticket !== seq.current) return null;
      setState({ status: 'error', data: null, error });
      return null;
    }
  }, []);

  const reset = useCallback(() => {
    seq.current++;
    setState({ status: 'idle', data: null, error: null });
  }, []);

  const setData = useCallback((data: T) => {
    seq.current++;
    setState({ status: 'success', data, error: null });
  }, []);

  return { ...state, run, reset, setData };
}
