"use client";

import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import { LogOut } from "lucide-react";

import { Wordmark } from "@/components/brand/wordmark";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { Button } from "@/components/ui/button";
import { logout } from "@/lib/api/auth";
import { cn } from "@/lib/utils";

interface TopNavProps {
  email: string;
}

const NAV_LINKS = [
  { href: "/", label: "Übersicht" },
  { href: "/invoices", label: "Rechnungen" },
  { href: "/exports", label: "Export" },
] as const;

export function TopNav({ email }: TopNavProps): React.JSX.Element {
  const router = useRouter();
  const pathname = usePathname();

  async function handleLogout(): Promise<void> {
    await logout();
    router.replace("/login");
    router.refresh();
  }

  return (
    <header className="sticky top-0 z-20 border-b border-border bg-background/90 backdrop-blur">
      <div className="mx-auto flex h-14 w-full max-w-[1280px] items-center justify-between px-4 md:px-6">
        <div className="flex items-center gap-6">
          <Wordmark />
          <nav className="flex items-center gap-1" aria-label="Hauptnavigation">
            {NAV_LINKS.map(({ href, label }) => {
              const isActive = pathname === href || (href !== "/" && pathname.startsWith(`${href}/`));
              return (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-accent text-accent-foreground"
                      : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                  )}
                  aria-current={isActive ? "page" : undefined}
                >
                  {label}
                </Link>
              );
            })}
          </nav>
        </div>
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
