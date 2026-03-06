import { useState, useEffect, useCallback, useRef } from "react";
import { get, getErrorMessage } from "../api/client";

type UseFetchOptions = {
  pollIntervalMs?: number;
  timeoutMs?: number;
};

export function useFetch<T>(
  path: string | null,
  options: UseFetchOptions = {},
) {
  const { pollIntervalMs, timeoutMs } = options;
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(!!path);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">(
    path ? "loading" : "idle",
  );
  const controllerRef = useRef<AbortController | null>(null);

  const fetchData = useCallback(async () => {
    if (!path) {
      controllerRef.current?.abort();
      controllerRef.current = null;
      setData(null);
      setError(null);
      setLoading(false);
      setStatus("idle");
      return null;
    }

    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;

    setLoading(true);
    setError(null);
    setStatus("loading");
    try {
      const result = await get<T>(path, {
        signal: controller.signal,
        timeoutMs,
      });
      if (!controller.signal.aborted) {
        setData(result);
        setStatus("success");
      }
      return result;
    } catch (e) {
      if (
        controller.signal.aborted ||
        (e instanceof Error && e.name === "AbortError")
      ) {
        return null;
      }

      if (!controller.signal.aborted) {
        setError(getErrorMessage(e));
        setStatus("error");
      }
      return null;
    } finally {
      if (controllerRef.current === controller) {
        controllerRef.current = null;
      }
      if (!controller.signal.aborted) {
        setLoading(false);
      }
    }
  }, [path, timeoutMs]);

  useEffect(() => {
    if (!path) {
      controllerRef.current?.abort();
      controllerRef.current = null;
      setData(null);
      setError(null);
      setLoading(false);
      setStatus("idle");
      return;
    }

    void fetchData();
    if (!pollIntervalMs) {
      return () => {
        controllerRef.current?.abort();
        controllerRef.current = null;
      };
    }

    const intervalId = window.setInterval(() => {
      void fetchData();
    }, pollIntervalMs);

    return () => {
      window.clearInterval(intervalId);
      controllerRef.current?.abort();
      controllerRef.current = null;
    };
  }, [fetchData, path, pollIntervalMs]);

  return { data, loading, error, refetch: fetchData, status };
}
