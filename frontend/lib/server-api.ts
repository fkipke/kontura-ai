import "server-only";

import { config } from "@/lib/config";

interface ServerFetchOptions {
  method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  token?: string;
  body?: BodyInit | null;
  contentType?: string;
  headers?: Record<string, string>;
}

export async function apiServerFetch(
  path: string,
  options: ServerFetchOptions,
): Promise<unknown> {
  const headers = new Headers(options.headers);
  if (options.contentType) {
    headers.set("Content-Type", options.contentType);
  }
  if (options.token) {
    headers.set("Authorization", `Bearer ${options.token}`);
  }

  const response = await fetch(`${config.apiBaseUrl}${path}`, {
    method: options.method,
    headers,
    body: options.body,
    cache: "no-store",
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? `Request fehlgeschlagen (${response.status})`);
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}
