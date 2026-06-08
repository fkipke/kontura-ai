import { NextResponse } from "next/server";

import { handleAuthTokenResponse } from "@/app/api/auth/_token-response";
import { config } from "@/lib/config";

export async function POST(request: Request): Promise<NextResponse> {
  const body = (await request.json().catch(() => null)) as unknown;

  const response = await fetch(`${config.apiBaseUrl}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });

  return handleAuthTokenResponse(response);
}
