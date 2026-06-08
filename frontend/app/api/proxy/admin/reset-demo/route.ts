import { type NextResponse } from "next/server";

import { forwardApiRequest } from "@/app/api/proxy/_forward";

export async function POST(request: Request): Promise<NextResponse> {
  return forwardApiRequest(request, "/api/v1/admin/reset-demo", { method: "POST" });
}
