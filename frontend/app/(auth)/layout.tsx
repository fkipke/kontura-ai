import { Wordmark } from "@/components/brand/wordmark";
import { Card, CardContent } from "@/components/ui/card";

export default function AuthLayout({ children }: { children: React.ReactNode }): React.JSX.Element {
  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-8 md:px-6">
      <Card className="w-full max-w-md">
        <CardContent className="space-y-6">
          <div className="space-y-1 text-center">
            <div className="inline-flex items-center justify-center">
              <Wordmark />
            </div>
            <p className="text-xs text-muted-foreground">Rechnungsbelege intelligent erfassen.</p>
          </div>
          {children}
        </CardContent>
      </Card>
    </main>
  );
}
