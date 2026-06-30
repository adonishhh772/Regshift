import { FetchTimeoutError } from "./networkErrors";

const DEFAULT_TIMEOUT_MS = 12_000;

export async function fetchWithTimeout(
  input: RequestInfo | URL,
  init?: RequestInit,
  timeoutMs: number = DEFAULT_TIMEOUT_MS
): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);

  try {
    return await fetch(input, {
      ...init,
      signal: controller.signal,
    });
  } catch (error) {
    if (controller.signal.aborted) {
      throw new FetchTimeoutError();
    }
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
}
