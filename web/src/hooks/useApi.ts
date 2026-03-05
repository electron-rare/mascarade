import { useState, useCallback } from "react";
import { ApiError } from "../api/client";

export function useApi<TResult, TArgs = void>(
  fn: (args: TArgs) => Promise<TResult>,
) {
  const [data, setData] = useState<TResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const execute = useCallback(
    async (args: TArgs) => {
      setLoading(true);
      setError(null);
      try {
        const result = await fn(args);
        setData(result);
        return result;
      } catch (e) {
        const msg = e instanceof ApiError ? e.message : "Unknown error";
        setError(msg);
        throw e;
      } finally {
        setLoading(false);
      }
    },
    [fn],
  );

  return { execute, data, loading, error };
}
