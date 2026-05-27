import { NextResponse } from "next/server";

import { readAuthToken } from "@/lib/auth/cookies";
import { config } from "@/lib/config";

function isPublicProxyTarget(path: string[]): boolean {
  const target = `/${path.join("/")}`;
  return (
    target === "/api/v1/auth/verify-email" ||
    target === "/api/v1/auth/resend-verification"
  );
}

async function forward(
  request: Request,
  params: Promise<{ path: string[] }>,
): Promise<NextResponse> {
  const token = await readAuthToken();
  const { path } = await params;

  if (!token && !isPublicProxyTarget(path)) {
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
  const target = `${config.apiBaseUrl}/${path.join("/")}${inputUrl.search}`;

  const headers = new Headers(request.headers);
  if (token) {
    headers.set("Authorization", "Bearer " + token);
  } else {
    headers.delete("Authorization");
  }
  headers.delete("host");

  const body =
    request.method === "GET" || request.method === "HEAD"
      ? null
      : await request.arrayBuffer();

  const response = await fetch(target, {
    method: request.method,
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

export async function GET(
  request: Request,
  context: { params: Promise<{ path: string[] }> },
): Promise<NextResponse> {
  return forward(request, context.params);
}

export async function POST(
  request: Request,
  context: { params: Promise<{ path: string[] }> },
): Promise<NextResponse> {
  return forward(request, context.params);
}

export async function PUT(
  request: Request,
  context: { params: Promise<{ path: string[] }> },
): Promise<NextResponse> {
  return forward(request, context.params);
}

export async function PATCH(
  request: Request,
  context: { params: Promise<{ path: string[] }> },
): Promise<NextResponse> {
  return forward(request, context.params);
}

export async function DELETE(
  request: Request,
  context: { params: Promise<{ path: string[] }> },
): Promise<NextResponse> {
  return forward(request, context.params);
}
