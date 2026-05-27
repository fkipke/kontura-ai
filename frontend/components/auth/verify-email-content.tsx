"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiClientError } from "@/lib/api/client";
import { useResendVerification, useVerifyEmail } from "@/lib/api/auth";

type VerifyState = "loading" | "success" | "error";

export function VerifyEmailContent(): React.JSX.Element {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const { mutateAsync: verifyEmail, error: verifyErrorRaw } = useVerifyEmail();
  const {
    mutateAsync: resendVerification,
    isPending: resendPending,
    isSuccess: resendSuccess,
    error: resendErrorRaw,
  } = useResendVerification();

  const [verifyState, setVerifyState] = useState<VerifyState>(token ? "loading" : "error");
  const [email, setEmail] = useState("");
  const [tenantSlug, setTenantSlug] = useState("");

  useEffect(() => {
    if (!token) {
      return;
    }
    verifyEmail({ token })
      .then(() => setVerifyState("success"))
      .catch(() => setVerifyState("error"));
  }, [token, verifyEmail]);

  const verifyError = verifyErrorRaw instanceof ApiClientError ? verifyErrorRaw.detail : null;
  const resendError = resendErrorRaw instanceof ApiClientError ? resendErrorRaw.detail : null;

  return (
    <div className="space-y-4">
      {verifyState === "loading" && (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">E-Mail wird verifiziert…</p>
          <div className="h-4 w-full animate-pulse rounded bg-muted" />
          <div className="h-4 w-2/3 animate-pulse rounded bg-muted" />
        </div>
      )}

      {verifyState === "success" && (
        <div className="space-y-4">
          <p className="rounded-lg border border-green-500/25 bg-green-500/10 p-3 text-sm text-green-700">
            ✅ E-Mail-Adresse bestätigt. Du kannst dich jetzt anmelden.
          </p>
          <Link href="/login">
            <Button className="w-full" type="button">
              Zur Anmeldung
            </Button>
          </Link>
        </div>
      )}

      {verifyState === "error" && (
        <div className="space-y-4">
          <p className="rounded-lg border border-destructive/25 bg-destructive/10 p-3 text-sm text-destructive">
            {verifyError ??
              "Der Verifikationslink ist ungültig oder abgelaufen. Fordere hier einen neuen Link an."}
          </p>

          <div className="space-y-2">
            <Label htmlFor="resend-email">E-Mail</Label>
            <Input
              id="resend-email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="resend-tenant">Firmen-Kennung</Label>
            <Input
              id="resend-tenant"
              autoComplete="organization"
              value={tenantSlug}
              onChange={(event) => setTenantSlug(event.target.value)}
            />
          </div>
          <Button
            className="w-full"
            type="button"
            disabled={resendPending}
            onClick={async () => {
              await resendVerification({ email, tenant_slug: tenantSlug });
            }}
          >
            {resendPending ? "Link wird gesendet…" : "Neuen Verifikationslink senden"}
          </Button>
          {resendSuccess && (
            <p className="text-sm text-green-600">Falls ein passendes Konto existiert, wurde ein Link gesendet.</p>
          )}
          {resendError && (
            <p className="rounded-lg border border-destructive/25 bg-destructive/10 p-3 text-sm text-destructive">
              {resendError}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
