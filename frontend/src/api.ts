import { useCallback, useEffect, useState } from "react";
export async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(path, {
    ...options,
    cache: "no-store",
    signal: options.signal ?? AbortSignal.timeout(12000),
  });
  const data = await response.json();
  if (!response.ok)
    throw new Error(data.error || `Request failed (${response.status}).`);
  return data as T;
}
export function write<T>(path: string, token: string, body: unknown) {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Hanni-Token": token },
    body: JSON.stringify(body),
  });
}
export function useResource<T>(path: string, interval: number) {
  const [data, setData] = useState<T | null>(null),
    [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const refresh = useCallback(() => setRevision((v) => v + 1), []);
  useEffect(() => {
    let live = true,
      timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    async function poll() {
      try {
        const result = await request<T>(path, {
          signal: AbortSignal.any([
            controller.signal,
            AbortSignal.timeout(12000),
          ]),
        });
        if (live) {
          setData(result);
          setError("");
        }
      } catch (e) {
        if (live)
          setError(e instanceof Error ? e.message : "Connection unavailable.");
      } finally {
        if (live && interval) timer = setTimeout(poll, interval);
      }
    }
    poll();
    return () => {
      live = false;
      controller.abort();
      clearTimeout(timer);
    };
  }, [path, interval, revision]);
  return { data, error, refresh, setData };
}
