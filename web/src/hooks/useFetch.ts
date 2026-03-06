import { useState, useEffect, useCallback, useRef } from "react";
import { get, ApiError } from "../api/client";

export function useFetch<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(!!path);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">(
    path ? "loading" : "idle",
  );
  const controllerRef = useRef<AbortController | null>(null);

  const fetchData = useCallback(async () => {
    if (!path) return;
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;

    setLoading(true);
    setError(null);
    setStatus("loading");
    try {
      const result = await get<T>(path);
      if (!controller.signal.aborted) {
        setData(result);
        setStatus("success");
      }
    } catch (e) {
      if (!controller.signal.aborted) {
        setError(e instanceof ApiError ? e.message : "Unknown error");
        setStatus("error");
      }
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false);
      }
    }
  }, [path]);

  useEffect(() => {
    fetchData();
    return () => {
      controllerRef.current?.abort();
    };
  }, [fetchData]);

  return { data, loading, error, refetch: fetchData, status };
}
