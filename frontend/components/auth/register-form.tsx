"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiClientError } from "@/lib/api/client";
import { useRegister } from "@/lib/api/auth";

const registerSchema = z.object({
  email: z.string().email("Bitte gib eine gültige E-Mail-Adresse ein."),
  password: z.string().min(12, "Das Passwort muss mindestens 12 Zeichen haben."),
  tenant_slug: z.string().min(2, "Tenant-Slug ist erforderlich."),
  tenant_display_name: z.string().min(1, "Mandantenname ist erforderlich."),
});

type RegisterFormValues = z.infer<typeof registerSchema>;

export function RegisterForm(): React.JSX.Element {
  const router = useRouter();
  const mutation = useRegister();

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
        <Label htmlFor="register-email">E-Mail</Label>
        <Input id="register-email" autoComplete="email" {...form.register("email")} />
      </div>
      <div className="space-y-2">
        <Label htmlFor="register-password">Passwort</Label>
        <Input id="register-password" type="password" autoComplete="new-password" {...form.register("password")} />
      </div>
      <div className="space-y-2">
        <Label htmlFor="register-tenant">Tenant-Slug</Label>
        <Input id="register-tenant" autoComplete="organization" {...form.register("tenant_slug")} />
      </div>
      <div className="space-y-2">
        <Label htmlFor="register-name">Mandantenname</Label>
        <Input id="register-name" {...form.register("tenant_display_name")} />
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
