import { type NextResponse } from "next/server";

import { forwardApiRequest } from "@/app/api/proxy/_forward";

export async function GET(request: Request): Promise<NextResponse> {
  return forwardApiRequest(request, "/api/v1/dashboard/cashflow", {
    method: "GET",
    query: { months: 12 },
  });
}
