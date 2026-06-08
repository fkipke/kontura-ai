import { NextResponse } from "next/server";

import { problemDetailSchema, tokenResponseSchema } from "@/lib/api/schemas";
import { writeAuthToken } from "@/lib/auth/cookies";

export async function handleAuthTokenResponse(response: Response): Promise<NextResponse> {
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
