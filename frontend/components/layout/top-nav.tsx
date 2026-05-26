"use client";

import { useRouter } from "next/navigation";
import { LogOut } from "lucide-react";

import { Wordmark } from "@/components/brand/wordmark";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { Button } from "@/components/ui/button";
import { logout } from "@/lib/api/auth";

interface TopNavProps {
  email: string;
}

export function TopNav({ email }: TopNavProps): React.JSX.Element {
  const router = useRouter();

  async function handleLogout(): Promise<void> {
    await logout();
    router.replace("/login");
    router.refresh();
  }

  return (
    <header className="sticky top-0 z-20 border-b border-border bg-background/90 backdrop-blur">
      <div className="mx-auto flex h-14 w-full max-w-[1280px] items-center justify-between px-4 md:px-6">
        <Wordmark />
        <div className="flex items-center gap-2">
          <span className="hidden text-sm text-muted-foreground sm:inline">{email}</span>
          <ThemeToggle />
          <Button type="button" variant="ghost" size="sm" onClick={handleLogout}>
            <LogOut className="mr-1 h-4 w-4" aria-hidden />
            Abmelden
          </Button>
        </div>
      </div>
    </header>
  );
}
