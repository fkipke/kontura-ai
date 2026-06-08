import { redirect } from "next/navigation";

import { DemoBanner } from "@/components/layout/demo-banner";
import { TopNav } from "@/components/layout/top-nav";
import { apiServerFetch } from "@/lib/server-api";
import { readAuthToken } from "@/lib/auth/cookies";
import { meResponseSchema } from "@/lib/api/schemas";

export default async function AppLayout({ children }: { children: React.ReactNode }): Promise<React.JSX.Element> {
  const token = await readAuthToken();
  if (!token) {
    redirect("/login");
  }

  let email = "";
  try {
    const me = await apiServerFetch("/api/v1/auth/me", {
      method: "GET",
      token,
    });
    email = meResponseSchema.parse(me).email;
  } catch {
    redirect("/login");
  }

  return (
    <div className="min-h-screen">
      <TopNav email={email} />
      {process.env.NEXT_PUBLIC_DEMO_MODE === "true" ? <DemoBanner /> : null}
      <div className="mx-auto w-full max-w-[1280px] px-4 py-6 md:px-6">{children}</div>
    </div>
  );
}
