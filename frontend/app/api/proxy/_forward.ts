import { NextResponse } from "next/server";

import { readAuthToken } from "@/lib/auth/cookies";
import { config } from "@/lib/config";

interface ForwardOptions {
  method?: "GET" | "POST";
  query?: Record<string, string | number | undefined>;
  requireAuth?: boolean;
}

export async function forwardApiRequest(
  request: Request,
  path: string,
  options: ForwardOptions = {},
): Promise<NextResponse> {
  const token = await readAuthToken();
  const requireAuth = options.requireAuth ?? true;

  if (!token && requireAuth) {
    return NextResponse.json(
      {
        type: "about:blank",
        title: "Unauthorized",
        status: 401,
        detail: "Nicht angemeldet.",
      },
      { status: 401 },
    );
  }

  const inputUrl = new URL(request.url);
  const targetUrl = new URL(`${config.apiBaseUrl}${path}`);

  for (const [key, value] of Object.entries(options.query ?? {})) {
    if (value !== undefined && value !== null && `${value}`.length > 0) {
      targetUrl.searchParams.set(key, String(value));
    }
  }

  inputUrl.searchParams.forEach((value, key) => {
    if (!targetUrl.searchParams.has(key)) {
      targetUrl.searchParams.append(key, value);
    }
  });

  const headers = new Headers(request.headers);
  if (token) {
    headers.set("Authorization", "Bearer " + token);
  } else {
    headers.delete("Authorization");
  }
  headers.delete("host");

  const method = options.method ?? (request.method as "GET" | "POST");
  const body = method === "GET" ? null : await request.arrayBuffer();

  const response = await fetch(targetUrl.toString(), {
    method,
    headers,
    body,
    cache: "no-store",
  });

  const responseHeaders = new Headers(response.headers);
  responseHeaders.delete("content-encoding");
  responseHeaders.delete("transfer-encoding");

  return new NextResponse(response.body, {
    status: response.status,
    headers: responseHeaders,
  });
}
