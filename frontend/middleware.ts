import { NextResponse, type NextRequest } from "next/server";

import { config as appConfig } from "@/lib/config";

const PUBLIC_ROUTES = ["/login", "/register", "/verify-email"];

function isPublicRoute(pathname: string): boolean {
  return PUBLIC_ROUTES.some((route) => pathname === route || pathname.startsWith(`${route}/`));
}

export function middleware(request: NextRequest): NextResponse {
  const token = request.cookies.get(appConfig.authCookieName)?.value;
  const pathname = request.nextUrl.pathname;

  if (pathname === "/") {
    if (!token) {
      return NextResponse.redirect(new URL("/login", request.url));
    }
    return NextResponse.next();
  }

  if (isPublicRoute(pathname) && token) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  if (!isPublicRoute(pathname) && !pathname.startsWith("/api") && !token) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
