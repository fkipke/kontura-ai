import { problemDetailSchema, type ProblemDetail } from "@/lib/api/schemas";

export class ApiClientError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
    public readonly requestId: string | null,
    public readonly errors: Array<Record<string, unknown>>,
    public readonly problem: ProblemDetail | null,
  ) {
    super(detail);
    this.name = "ApiClientError";
  }
}

async function parseProblem(response: Response): Promise<ProblemDetail | null> {
  const body = (await response.json().catch(() => null)) as unknown;
  const parsed = problemDetailSchema.safeParse(body);
  if (!parsed.success) {
    return null;
  }
  return parsed.data;
}

export async function apiRequest<T>(
  input: RequestInfo | URL,
  init: RequestInit,
  parser: (value: unknown) => T,
): Promise<T> {
  const response = await fetch(input, init);
  if (!response.ok) {
    const problem = await parseProblem(response);
    throw new ApiClientError(
      response.status,
      problem?.detail ?? problem?.title ?? "Unbekannter Fehler",
      problem?.request_id ?? response.headers.get("x-request-id"),
      problem?.errors ?? [],
      problem,
    );
  }

  if (response.status === 204) {
    return parser(undefined);
  }

  const raw = (await response.json().catch(() => null)) as unknown;
  return parser(raw);
}
