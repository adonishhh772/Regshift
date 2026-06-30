interface FastApiValidationError {
  type: string;
  loc: (string | number)[];
  msg: string;
  input?: unknown;
}

interface FastApiErrorBody {
  detail?: string | FastApiValidationError[];
}

function formatValidationError(error: FastApiValidationError): string {
  const field = error.loc.filter((part) => typeof part === "string" && part !== "body").join(".");

  if (error.type === "string_too_short" && field === "text") {
    return "Describe your business change in at least 10 characters before continuing.";
  }

  if (error.type === "missing" && field === "session_id") {
    return "No active session. Run classify first.";
  }

  if (field) {
    return `${field.replace(/_/g, " ")}: ${error.msg}`;
  }

  return error.msg;
}

function extractMessageFromObject(value: Record<string, unknown>): string | null {
  for (const key of ["detail", "message", "msg", "error"]) {
    const candidate = value[key];
    if (typeof candidate === "string" && candidate.trim()) {
      return candidate;
    }
  }
  return null;
}

export function parseApiErrorMessage(raw: string): string {
  const trimmed = raw.trim();

  if (!trimmed) {
    return "Something went wrong. Please try again.";
  }

  try {
    const parsed = JSON.parse(trimmed) as FastApiErrorBody & Record<string, unknown>;

    if (typeof parsed.detail === "string") {
      return parsed.detail;
    }

    if (Array.isArray(parsed.detail) && parsed.detail.length > 0) {
      return parsed.detail.map(formatValidationError).join(" ");
    }

    const objectMessage = extractMessageFromObject(parsed);
    if (objectMessage) {
      return objectMessage;
    }
  } catch {
    /* plain text error body */
  }

  if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
    return "Something went wrong. Check your input and try again.";
  }

  return trimmed.length > 240 ? `${trimmed.slice(0, 240)}…` : trimmed;
}
