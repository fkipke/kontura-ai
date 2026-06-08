"use client";

import { useRouter } from "next/navigation";

import { ExtractionMethodBadge } from "@/components/invoices/extraction-method-badge";
import { InvoiceFilterBar } from "@/components/invoices/filter-bar";
import { InvoicePagination } from "@/components/invoices/pagination";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import { useInvoices, useInvoiceVendors } from "@/lib/invoices/queries";
import { useInvoiceUrlState } from "@/lib/invoices/url-state";

const invoiceStatusMap: Record<
  string,
  { label: string; variant: "secondary" | "warning" | "success" | "destructive" }
> = {
  received: { label: "Eingegangen", variant: "secondary" },
  processing: { label: "Verarbeitung", variant: "warning" },
  extracted: { label: "Extrahiert", variant: "warning" },
  reviewed: { label: "Geprüft", variant: "success" },
  booked: { label: "Verbucht", variant: "success" },
  not_an_invoice: { label: "Keine Rechnung", variant: "destructive" },
};

function ReviewedCell({
  isReviewed,
  reviewedAt,
}: {
  isReviewed: boolean | undefined;
  reviewedAt: string | null | undefined;
}): React.JSX.Element {
  if (isReviewed) {
    return <span className="text-emerald-600">✓ Geprüft am {formatGermanDate(reviewedAt)}</span>;
  }
  return <span>—</span>;
}

export default function InvoicesPage(): React.JSX.Element {
  const router = useRouter();
  const { filters, setFilter, setPage, setPageSize, resetFilters } = useInvoiceUrlState();
  const invoices = useInvoices(filters);
  const vendors = useInvoiceVendors();

  return (
    <main className="space-y-4">
      <header className="space-y-1">
        <h1 className="text-3xl font-semibold tracking-tight">Eingangsrechnungen</h1>
        <p className="text-sm text-muted-foreground">Filterbar, Suche und Pagination für die Demo.</p>
      </header>

      <InvoiceFilterBar
        filters={filters}
        vendors={vendors.data ?? []}
        onSetFilter={setFilter}
        onReset={resetFilters}
      />

      <Card className="min-h-[520px] transition-opacity duration-200">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Status</TableHead>
                <TableHead>Rechnungsnr.</TableHead>
                <TableHead>Lieferant</TableHead>
                <TableHead>Datum</TableHead>
                <TableHead className="text-right">Betrag</TableHead>
                <TableHead>Extraktionsmethode</TableHead>
                <TableHead>Geprüft</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {invoices.isLoading
                ? Array.from({ length: 8 }).map((_, index) => (
                    <TableRow key={`skeleton-${index}`}>
                      <TableCell>
                        <Skeleton className="h-6 w-20" />
                      </TableCell>
                      <TableCell><Skeleton className="h-5 w-28" /></TableCell>
                      <TableCell><Skeleton className="h-5 w-36" /></TableCell>
                      <TableCell><Skeleton className="h-5 w-24" /></TableCell>
                      <TableCell className="text-right"><Skeleton className="ml-auto h-5 w-24" /></TableCell>
                      <TableCell><Skeleton className="h-6 w-28" /></TableCell>
                      <TableCell><Skeleton className="h-5 w-24" /></TableCell>
                    </TableRow>
                  ))
                : (invoices.data?.items ?? []).map((invoice) => (
                    <TableRow key={invoice.id} className="cursor-pointer" onClick={() => router.push(`/invoices/${invoice.id}`)}>
                      <TableCell>
                        <Badge variant={(invoiceStatusMap[invoice.status]?.variant ?? "secondary")}>
                          {invoiceStatusMap[invoice.status]?.label ?? invoice.status}
                        </Badge>
                      </TableCell>
                      <TableCell>{invoice.invoice_number ?? "—"}</TableCell>
                      <TableCell>{invoice.vendor_name ?? "—"}</TableCell>
                      <TableCell>{formatGermanDate(invoice.invoice_date)}</TableCell>
                      <TableCell className="text-right font-tnum">{formatCurrency(invoice.total_amount)}</TableCell>
                      <TableCell>
                        <ExtractionMethodBadge method={invoice.extraction_method ?? null} />
                      </TableCell>
                      <TableCell>
                        <ReviewedCell isReviewed={invoice.is_reviewed} reviewedAt={invoice.reviewed_at} />
                      </TableCell>
                    </TableRow>
                  ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {!invoices.isLoading && (invoices.data?.items.length ?? 0) === 0 ? (
        <Card>
          <CardContent className="space-y-3 py-8 text-center">
            <p className="font-medium">Keine Rechnungen gefunden</p>
            <p className="text-sm text-muted-foreground">Passe die Filter an oder lade die erste Rechnung hoch.</p>
            <div>
              <Button type="button" variant="outline" onClick={resetFilters}>
                Filter zurücksetzen
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : null}

      <InvoicePagination
        page={filters.page}
        pageSize={filters.pageSize}
        total={invoices.data?.total ?? 0}
        totalPages={invoices.data?.totalPages ?? 1}
        onPageChange={setPage}
        onPageSizeChange={setPageSize}
      />
    </main>
  );
}
