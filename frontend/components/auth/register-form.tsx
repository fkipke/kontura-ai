"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiClientError } from "@/lib/api/client";
import { useRegister, useResendVerification } from "@/lib/api/auth";

const registerSchema = z.object({
  email: z.string().email("Bitte gib eine gültige E-Mail-Adresse ein."),
  password: z.string().min(12, "Das Passwort muss mindestens 12 Zeichen haben."),
  tenant_slug: z
    .string()
    .min(2, "Firmen-Kennung ist erforderlich.")
    .regex(/^[a-z0-9-]+$/, "Nur Kleinbuchstaben, Zahlen und Bindestriche erlaubt."),
  tenant_display_name: z.string().min(1, "Firmenname ist erforderlich."),
});

type RegisterFormValues = z.infer<typeof registerSchema>;

export function RegisterForm(): React.JSX.Element {
  const mutation = useRegister();
  const resendMutation = useResendVerification();
  const [submitted, setSubmitted] = useState(false);
  const [submittedEmail, setSubmittedEmail] = useState("");

  const form = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      email: "",
      password: "",
      tenant_slug: "",
      tenant_display_name: "",
    },
  });

  const inlineError = mutation.error instanceof ApiClientError ? mutation.error.detail : null;
  const resendError = resendMutation.error instanceof ApiClientError ? resendMutation.error.detail : null;

  if (submitted) {
    return (
      <div className="space-y-4">
        <p className="rounded-lg border border-primary/30 bg-primary/10 p-3 text-sm">
          Wir haben dir eine E-Mail an <strong>{submittedEmail}</strong> geschickt. Bitte öffne den Link in der Mail,
          um dein Konto zu aktivieren.
        </p>
        <Button
          className="w-full"
          type="button"
          variant="outline"
          disabled={resendMutation.isPending}
          onClick={async () => {
            await resendMutation.mutateAsync({
              email: submittedEmail,
              tenant_slug: form.getValues("tenant_slug"),
            });
          }}
        >
          {resendMutation.isPending ? "Link wird gesendet…" : "Keine Mail erhalten? Erneut senden"}
        </Button>
        {resendMutation.isSuccess && <p className="text-sm text-green-600">Neuer Verifikationslink wurde gesendet.</p>}
        {resendError && (
          <p className="rounded-lg border border-destructive/25 bg-destructive/10 p-3 text-sm text-destructive">
            {resendError}
          </p>
        )}
        <p className="text-sm text-muted-foreground">
          <Link className="text-primary hover:underline" href="/login">
            Zur Anmeldung
          </Link>
        </p>
      </div>
    );
  }

  return (
    <form
      className="space-y-4"
      onSubmit={form.handleSubmit(async (values) => {
        const response = await mutation.mutateAsync(values);
        if (response.email_verification_required) {
          setSubmittedEmail(values.email);
          setSubmitted(true);
        }
      })}
      noValidate
    >
      <div className="space-y-2">
        <Label htmlFor="register-email">E-Mail</Label>
        <Input id="register-email" autoComplete="email" {...form.register("email")} />
      </div>
      <div className="space-y-2">
        <Label htmlFor="register-password">Passwort</Label>
        <Input id="register-password" type="password" autoComplete="new-password" {...form.register("password")} />
      </div>
      <div className="space-y-2">
        <Label htmlFor="register-tenant">Firmen-Kennung</Label>
        <Input
          id="register-tenant"
          autoComplete="organization"
          aria-describedby="register-tenant-hint"
          {...form.register("tenant_slug")}
        />
        <p id="register-tenant-hint" className="text-xs text-muted-foreground">
          Kurzname für die URL — nur Kleinbuchstaben, Zahlen und Bindestriche (mind. 2 Zeichen). Beispiel: meine-firma
        </p>
        {form.formState.errors.tenant_slug && (
          <p className="text-xs text-destructive">{form.formState.errors.tenant_slug.message}</p>
        )}
      </div>
      <div className="space-y-2">
        <Label htmlFor="register-name">Firmenname</Label>
        <Input id="register-name" placeholder="Meine Firma GmbH" {...form.register("tenant_display_name")} />
        {form.formState.errors.tenant_display_name && (
          <p className="text-xs text-destructive">{form.formState.errors.tenant_display_name.message}</p>
        )}
      </div>

      {form.formState.errors.root?.message && (
        <p className="text-xs text-destructive">{form.formState.errors.root.message}</p>
      )}
      {inlineError && (
        <p className="rounded-lg border border-destructive/25 bg-destructive/10 p-3 text-sm text-destructive">
          {inlineError}
        </p>
      )}

      <Button className="w-full" type="submit" disabled={mutation.isPending}>
        {mutation.isPending ? "Konto wird erstellt…" : "Konto erstellen"}
      </Button>

      <p className="text-sm text-muted-foreground">
        Bereits Kunde?{" "}
        <Link className="text-primary hover:underline" href="/login">
          Anmelden →
        </Link>
      </p>
    </form>
  );
}
