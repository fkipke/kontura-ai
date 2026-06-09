import { StatusBadge } from "@/components/invoices/status-badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatCurrency, formatGermanDate } from "@/lib/format";
import type { InvoiceListItem } from "@/lib/api/schemas";

interface InvoicesListTableProps {
  rows: InvoiceListItem[];
}

export function InvoicesListTable({ rows }: InvoicesListTableProps): React.JSX.Element {
  if (rows.length === 0) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-muted-foreground">
          Keine Rechnungen für die ausgewählten Filter gefunden.
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Status</TableHead>
              <TableHead>Rechnungsnummer</TableHead>
              <TableHead>Lieferant</TableHead>
              <TableHead>Datum</TableHead>
              <TableHead className="text-right">Betrag</TableHead>
              <TableHead>Aktualisiert</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.id}>
                <TableCell>
                  <StatusBadge status={row.status} />
                </TableCell>
                <TableCell>{row.invoice_number}</TableCell>
                <TableCell>{row.vendor_name}</TableCell>
                <TableCell>{formatGermanDate(row.invoice_date)}</TableCell>
                <TableCell className="text-right font-tnum">{formatCurrency(row.total_amount)}</TableCell>
                <TableCell>{formatGermanDate(row.updated_at)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
