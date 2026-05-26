import { NextResponse } from "next/server";

import { clearAuthToken } from "@/lib/auth/cookies";

export async function POST(): Promise<NextResponse> {
  await clearAuthToken();
  return NextResponse.json({ ok: true }, { status: 200 });
}
