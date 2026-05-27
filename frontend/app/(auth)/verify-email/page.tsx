import { Suspense } from "react";

import { VerifyEmailContent } from "@/components/auth/verify-email-content";

export default function VerifyEmailPage(): React.JSX.Element {
  return (
    <Suspense fallback={<p className="text-sm text-muted-foreground">E-Mail wird verifiziert…</p>}>
      <VerifyEmailContent />
    </Suspense>
  );
}
