"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiClientError } from "@/lib/api/client";
import { useLogin, useResendVerification } from "@/lib/api/auth";

const loginSchema = z.object({
  email: z.string().email("Bitte gib eine gültige E-Mail-Adresse ein."),
  password: z.string().min(1, "Passwort ist erforderlich."),
  tenant_slug: z.string().min(2, "Firmen-Kennung ist erforderlich."),
});

type LoginFormValues = z.infer<typeof loginSchema>;

export function LoginForm(): React.JSX.Element {
  const router = useRouter();
  const mutation = useLogin();
  const resendMutation = useResendVerification();

  const form = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: "",
      password: "",
      tenant_slug: "",
    },
  });

  const inlineError = mutation.error instanceof ApiClientError ? mutation.error.detail : null;
  const isEmailNotVerified =
    mutation.error instanceof ApiClientError && mutation.error.problem?.code === "email_not_verified";
  const resendError = resendMutation.error instanceof ApiClientError ? resendMutation.error.detail : null;

  return (
    <form
      className="space-y-4"
      onSubmit={form.handleSubmit(async (values) => {
        await mutation.mutateAsync(values);
        router.replace("/");
        router.refresh();
      })}
      noValidate
    >
      <div className="space-y-2">
        <Label htmlFor="login-email">E-Mail</Label>
        <Input id="login-email" autoComplete="email" {...form.register("email")} />
        {form.formState.errors.email && (
          <p className="text-xs text-destructive">{form.formState.errors.email.message}</p>
        )}
      </div>

      <div className="space-y-2">
        <Label htmlFor="login-password">Passwort</Label>
        <Input id="login-password" type="password" autoComplete="current-password" {...form.register("password")} />
        {form.formState.errors.password && (
          <p className="text-xs text-destructive">{form.formState.errors.password.message}</p>
        )}
      </div>

      <div className="space-y-2">
        <Label htmlFor="login-tenant">Firmen-Kennung</Label>
        <Input id="login-tenant" autoComplete="organization" {...form.register("tenant_slug")} />
        {form.formState.errors.tenant_slug && (
          <p className="text-xs text-destructive">{form.formState.errors.tenant_slug.message}</p>
        )}
      </div>

      {inlineError && (
        <p className="rounded-lg border border-destructive/25 bg-destructive/10 p-3 text-sm text-destructive">
          {inlineError}
        </p>
      )}

      {isEmailNotVerified && (
        <div className="space-y-2">
          <p className="rounded-lg border border-amber-500/25 bg-amber-500/10 p-3 text-sm text-amber-600">
            E-Mail-Adresse noch nicht bestätigt.
          </p>
          <Button
            className="w-full"
            type="button"
            variant="outline"
            disabled={resendMutation.isPending}
            onClick={async () => {
              await resendMutation.mutateAsync({
                email: form.getValues("email"),
                tenant_slug: form.getValues("tenant_slug"),
              });
              toast.success("Neuer Link wurde gesendet.");
            }}
          >
            {resendMutation.isPending ? "Link wird gesendet…" : "Verifikationslink erneut senden"}
          </Button>
          {resendError && (
            <p className="rounded-lg border border-destructive/25 bg-destructive/10 p-3 text-sm text-destructive">
              {resendError}
            </p>
          )}
        </div>
      )}

      <Button className="w-full" type="submit" disabled={mutation.isPending}>
        {mutation.isPending ? "Anmeldung läuft…" : "Anmelden"}
      </Button>

      <p className="text-sm text-muted-foreground">
        Noch kein Konto?{" "}
        <Link className="text-primary hover:underline" href="/register">
          Jetzt registrieren →
        </Link>
      </p>
    </form>
  );
}
