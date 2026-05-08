/**
 * Next.js Middleware — Route-Schutz auf Edge-Ebene.
 *
 * Wird VOR jedem Request ausgefuehrt, der zum konfigurierten "matcher"
 * passt. Liest Cookies, entscheidet ueber Redirect.
 *
 * Senior-Detail: Middleware laeuft im Edge Runtime (V8, kein Node-API).
 * Wir koennen hier KEINE Backend-Calls machen, KEIN @/lib/api importieren.
 * Nur reine Cookie-Logik. Echte Auth-Validierung passiert in der Page selbst.
 *
 * Routen-Strategie:
 *  - PUBLIC routes:  /login, /api/auth/*    → kein Schutz
 *  - PROTECTED:      alle anderen           → Cookie-Check
 *
 * Wenn ein eingeloggter User /login aufruft → redirect zu /dashboard.
 * (Sonst muesste er sich zwingend ausloggen, um die Login-Page zu sehen.)
 */

import { NextResponse, type NextRequest } from "next/server";

const AUTH_COOKIE_NAME = "access_token";

const PUBLIC_PATHS = ["/login"];
const PUBLIC_PATH_PREFIXES = ["/api/auth/"];

function isPublicPath(pathname: string): boolean {
  if (PUBLIC_PATHS.includes(pathname)) return true;
  return PUBLIC_PATH_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}

export function middleware(request: NextRequest): NextResponse {
  const { pathname } = request.nextUrl;
  const hasToken = request.cookies.has(AUTH_COOKIE_NAME);

  // Eingeloggter User auf /login? → ab zum Dashboard.
  if (pathname === "/login" && hasToken) {
    const url = request.nextUrl.clone();
    url.pathname = "/dashboard";
    return NextResponse.redirect(url);
  }

  // Public Path ohne Token? → durchlassen.
  if (isPublicPath(pathname)) {
    return NextResponse.next();
  }

  // Protected Path ohne Token? → ab zum Login (mit Rueckleit-Param).
  if (!hasToken) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    // Optional: damit nach Login zurueck zur urspruenglich gewollten Seite.
    url.searchParams.set("next", pathname);
    return NextResponse.redirect(url);
  }

  // Protected Path mit Token → durchlassen.
  return NextResponse.next();
}

/**
 * Welche Pfade triggern die Middleware?
 *
 * Wir excluden:
 *  - /_next/* (Next.js-Internas: JS-Chunks, Bilder)
 *  - statische Files mit Extension (favicon.ico, robots.txt, ...)
 *
 * Begruendung: Middleware laeuft pro Request. Wenn wir sie fuer 200
 * Static-Asset-Requests triggern, wuerde jede Page-Load 200x Middleware-
 * Code ausfuehren = unnoetige Latenz.
 */
export const config = {
  matcher: ["/((?!_next/|.*\\..*).*)"],
};