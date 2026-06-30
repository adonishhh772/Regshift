const REQUEST_TIMEOUT_MESSAGE = "Request timed out. The backend may be starting or unreachable.";
const BACKEND_UNREACHABLE_MESSAGE = "Unable to reach the backend. Check that the API is running on port 8000.";

function isAbortError(error: unknown): boolean {
  if (error instanceof DOMException && error.name === "AbortError") {
    return true;
  }
  if (error instanceof Error && error.name === "AbortError") {
    return true;
  }
  if (error instanceof Error && error.message.toLowerCase().includes("aborted")) {
    return true;
  }
  return false;
}

function isNetworkError(error: unknown): boolean {
  return error instanceof TypeError && error.message === "Failed to fetch";
}

export function normalizeFetchError(error: unknown): string {
  if (isAbortError(error)) {
    return REQUEST_TIMEOUT_MESSAGE;
  }
  if (isNetworkError(error)) {
    return BACKEND_UNREACHABLE_MESSAGE;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Something went wrong. Please try again.";
}

export class FetchTimeoutError extends Error {
  constructor(message: string = REQUEST_TIMEOUT_MESSAGE) {
    super(message);
    this.name = "FetchTimeoutError";
  }
}

export { BACKEND_UNREACHABLE_MESSAGE, REQUEST_TIMEOUT_MESSAGE };
