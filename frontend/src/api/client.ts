export const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "/api";

// SSE (EventSource) must bypass the Next.js proxy which buffers responses.
// In production, SSE hits the same origin; in dev, it needs the direct backend URL.
export const SSE_URL =
  process.env.NEXT_PUBLIC_SSE_URL ||
  (BASE_URL === "/api" ? "http://localhost:8501" : BASE_URL);

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiFetch<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "Unknown error");
    throw new ApiError(res.status, text);
  }
  return res.json() as Promise<T>;
}
