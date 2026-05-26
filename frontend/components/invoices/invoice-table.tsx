"use client";

import { useRouter } from "next/navigation";

import { StatusBadge } from "@/components/invoices/status-badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatCurrency, formatGermanDate } from "@/lib/format";
import { useExtractionStatuses } from "@/lib/api/invoiceFiles";
import type { InvoiceFile } from "@/lib/api/schemas";

interface InvoiceTableProps {
  rows: InvoiceFile[];
}

export function InvoiceTable({ rows }: InvoiceTableProps): React.JSX.Element {
  const router = useRouter();
  const sorted = [...rows].sort((a, b) => b.created_at.localeCompare(a.created_at));
  const extractionQueries = useExtractionStatuses(sorted.map((row) => row.id));

  if (rows.length === 0) {
    return (
      <Card>
        <CardContent className="space-y-2 py-10 text-center">
          <p className="text-sm font-medium">Noch keine Rechnungen hochgeladen.</p>
          <p className="text-sm text-muted-foreground">
            Ziehe eine PDF hierher oder klicke oben. ↑
          </p>
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
              <TableHead>Dateiname</TableHead>
              <TableHead>Lieferant</TableHead>
              <TableHead>Datum</TableHead>
              <TableHead className="text-right">Betrag</TableHead>
              <TableHead>Hochgeladen</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorted.map((row, index) => {
              const extraction = extractionQueries[index]?.data;
              const loadingExtraction = extractionQueries[index]?.isLoading ?? false;

              return (
                <TableRow
                  key={row.id}
                  className="cursor-pointer"
                  onClick={() => router.push(`/invoices/${row.id}`)}
                >
                  <TableCell>
                    <StatusBadge status={row.extraction_status} />
                  </TableCell>
                  <TableCell className="max-w-[280px] truncate">{row.filename}</TableCell>
                  <TableCell>
                    {loadingExtraction || row.extraction_status !== "completed" ? (
                      row.extraction_status === "pending" || row.extraction_status === "processing" ? (
                        <Skeleton className="h-4 w-28" />
                      ) : (
                        "—"
                      )
                    ) : (
                      extraction?.result?.vendor_name || "–"
                    )}
                  </TableCell>
                  <TableCell>
                    {row.extraction_status === "completed"
                      ? formatGermanDate(extraction?.result?.invoice_date ?? null)
                      : "—"}
                  </TableCell>
                  <TableCell className="text-right font-tnum">
                    {row.extraction_status === "completed"
                      ? formatCurrency(extraction?.result?.total_amount ?? null)
                      : row.extraction_status === "pending" ||
                          row.extraction_status === "processing"
                        ? "…"
                        : "—"}
                  </TableCell>
                  <TableCell>{formatGermanDate(row.created_at)}</TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
