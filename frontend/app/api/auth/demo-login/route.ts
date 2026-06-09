import { NextResponse } from "next/server";

import { problemDetailSchema, tokenResponseSchema } from "@/lib/api/schemas";
import { writeAuthToken } from "@/lib/auth/cookies";
import { config } from "@/lib/config";

export async function POST(): Promise<NextResponse> {
  const response = await fetch(`${config.apiBaseUrl}/api/v1/auth/demo-login`, {
    method: "POST",
    cache: "no-store",
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as unknown;
    const problem = problemDetailSchema.safeParse(payload);
    return NextResponse.json(problem.success ? problem.data : payload, {
      status: response.status,
    });
  }

  const token = tokenResponseSchema.parse((await response.json()) as unknown);
  await writeAuthToken(token.access_token, token.expires_in_seconds);

  return NextResponse.json({ ok: true }, { status: 200 });
}
