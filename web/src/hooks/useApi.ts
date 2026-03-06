import { useState, useCallback } from "react";
import { getErrorMessage } from "../api/client";

export function useApi<TResult, TArgs = void>(
  fn: (args: TArgs) => Promise<TResult>,
) {
  const [data, setData] = useState<TResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");

  const execute = useCallback(
    async (args: TArgs): Promise<TResult | undefined> => {
      setLoading(true);
      setError(null);
      setData(null);
      setStatus("loading");
      try {
        const result = await fn(args);
        setData(result);
        setStatus("success");
        return result;
      } catch (e) {
        setError(getErrorMessage(e));
        setStatus("error");
        return undefined;
      } finally {
        setLoading(false);
      }
    },
    [fn],
  );

  return { execute, data, loading, error, status };
}
