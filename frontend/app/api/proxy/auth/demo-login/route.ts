import { type NextResponse } from "next/server";

import { handleAuthTokenResponse } from "@/app/api/auth/_token-response";
import { config } from "@/lib/config";

export async function POST(): Promise<NextResponse> {
  const response = await fetch(`${config.apiBaseUrl}/api/v1/auth/demo-login`, {
    method: "POST",
    cache: "no-store",
  });

  return handleAuthTokenResponse(response);
}
