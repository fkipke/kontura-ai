/**
 * "/" — Root-Seite.
 *
 * Verhalten:
 *  - eingeloggt → /dashboard
 *  - nicht eingeloggt → /login
 *
 * Die eigentliche Cookie-Pruefung macht die Middleware. Wenn die Anfrage
 * hier ankommt (also der Cookie da ist), redirecten wir zum Dashboard.
 *
 * Hinweis: Die Middleware leitet "/" mit Token bereits zum Dashboard, wenn
 * man wollte. Wir setzen hier dennoch einen expliziten Redirect — sicherer
 * und klarer als Konvention.
 */

import { redirect } from "next/navigation";

import { readAuthToken } from "@/lib/auth";

export default async function HomePage() {
  const token = await readAuthToken();
  if (token) {
    redirect("/dashboard");
  }
  redirect("/login");
}