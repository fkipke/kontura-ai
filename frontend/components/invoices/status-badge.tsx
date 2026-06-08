import { Badge } from "@/components/ui/badge";
import type { InvoiceStatus } from "@/lib/api/schemas";

const statusMap: Record<InvoiceStatus, { label: string; variant: "warning" | "success" | "destructive" }> = {
  pending: { label: "Wartend", variant: "warning" },
  processing: { label: "Verarbeitung", variant: "warning" },
  completed: { label: "Fertig", variant: "success" },
  failed: { label: "Fehler", variant: "destructive" },
  not_an_invoice: { label: "Keine Rechnung", variant: "destructive" },
};

export function getStatusMeta(status: InvoiceStatus) {
  return statusMap[status];
}

export function StatusBadge({ status }: { status: InvoiceStatus }): React.JSX.Element {
  const meta = getStatusMeta(status);
  const pulse = status === "pending" || status === "processing";

  return (
    <Badge variant={meta.variant} className={pulse ? "animate-pulse" : undefined}>
      {meta.label}
    </Badge>
  );
}
