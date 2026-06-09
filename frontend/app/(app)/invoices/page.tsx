"use client";

import { useMemo, useState } from "react";

import { InvoicesListTable } from "@/components/invoices/invoices-list-table";
import { UploadDropzone } from "@/components/invoices/upload-dropzone";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useInvoicesList, useInvoiceVendors, type InvoicesListFilters } from "@/lib/api/invoices-list";

export default function InvoicesPage(): React.JSX.Element {
  const [draft, setDraft] = useState<InvoicesListFilters>({
    sortBy: "invoice_date",
    sortOrder: "desc",
    reviewed: "all",
    status: "all",
  });
  const [filters, setFilters] = useState<InvoicesListFilters>(draft);

  const vendors = useInvoiceVendors();
  const invoices = useInvoicesList(filters);

  const totalCount = invoices.data?.totalCount ?? 0;

  const sortedVendors = useMemo(
    () => [...(vendors.data ?? [])].sort((a, b) => a.localeCompare(b, "de")),
    [vendors.data],
  );

  function applyFilters(): void {
    setFilters(draft);
  }

  function resetFilters(): void {
    const base: InvoicesListFilters = {
      sortBy: "invoice_date",
      sortOrder: "desc",
      reviewed: "all",
      status: "all",
    };
    setDraft(base);
    setFilters(base);
  }

  return (
    <main className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-3xl font-semibold tracking-tight">Rechnungen</h1>
        <p className="text-sm text-muted-foreground">Filterbare Rechnungsübersicht für den aktuellen Tenant</p>
      </header>

      <UploadDropzone />

      <Card>
        <CardContent className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <div className="space-y-2 md:col-span-2 xl:col-span-2">
            <Label htmlFor="search">Suche</Label>
            <Input
              id="search"
              value={draft.search ?? ""}
              onChange={(event) => setDraft((prev) => ({ ...prev, search: event.target.value }))}
              placeholder="Rechnungsnummer oder Lieferant"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="status">Status</Label>
            <select
              id="status"
              className="h-9 w-full rounded-lg border border-border bg-background px-3 text-sm"
              value={draft.status ?? "all"}
              onChange={(event) => setDraft((prev) => ({ ...prev, status: event.target.value }))}
            >
              <option value="all">Alle</option>
              <option value="received">Eingegangen</option>
              <option value="booked">Gebucht</option>
              <option value="exported">Exportiert</option>
            </select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="reviewed">Geprüft</Label>
            <select
              id="reviewed"
              className="h-9 w-full rounded-lg border border-border bg-background px-3 text-sm"
              value={draft.reviewed ?? "all"}
              onChange={(event) =>
                setDraft((prev) => ({
                  ...prev,
                  reviewed: event.target.value as InvoicesListFilters["reviewed"],
                }))
              }
            >
              <option value="all">Alle</option>
              <option value="true">Ja</option>
              <option value="false">Nein</option>
            </select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="vendor">Lieferant</Label>
            <Input
              id="vendor"
              list="vendor-options"
              value={draft.vendor ?? ""}
              onChange={(event) => setDraft((prev) => ({ ...prev, vendor: event.target.value }))}
              placeholder="z. B. Telekom GmbH"
            />
            <datalist id="vendor-options">
              {sortedVendors.map((vendor) => (
                <option key={vendor} value={vendor} />
              ))}
            </datalist>
          </div>

          <div className="space-y-2">
            <Label htmlFor="date-from">Datum von</Label>
            <Input
              id="date-from"
              type="date"
              value={draft.dateFrom ?? ""}
              onChange={(event) => setDraft((prev) => ({ ...prev, dateFrom: event.target.value }))}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="date-to">Datum bis</Label>
            <Input
              id="date-to"
              type="date"
              value={draft.dateTo ?? ""}
              onChange={(event) => setDraft((prev) => ({ ...prev, dateTo: event.target.value }))}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="amount-min">Betrag min</Label>
            <Input
              id="amount-min"
              type="number"
              min="0"
              step="0.01"
              value={draft.amountMin ?? ""}
              onChange={(event) => setDraft((prev) => ({ ...prev, amountMin: event.target.value }))}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="amount-max">Betrag max</Label>
            <Input
              id="amount-max"
              type="number"
              min="0"
              step="0.01"
              value={draft.amountMax ?? ""}
              onChange={(event) => setDraft((prev) => ({ ...prev, amountMax: event.target.value }))}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="sort-by">Sortieren nach</Label>
            <select
              id="sort-by"
              className="h-9 w-full rounded-lg border border-border bg-background px-3 text-sm"
              value={draft.sortBy ?? "invoice_date"}
              onChange={(event) =>
                setDraft((prev) => ({
                  ...prev,
                  sortBy: event.target.value as InvoicesListFilters["sortBy"],
                }))
              }
            >
              <option value="invoice_date">Rechnungsdatum</option>
              <option value="total_amount">Betrag</option>
              <option value="vendor_name">Lieferant</option>
              <option value="invoice_number">Rechnungsnummer</option>
              <option value="status">Status</option>
              <option value="created_at">Erstellt am</option>
            </select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="sort-order">Reihenfolge</Label>
            <select
              id="sort-order"
              className="h-9 w-full rounded-lg border border-border bg-background px-3 text-sm"
              value={draft.sortOrder ?? "desc"}
              onChange={(event) =>
                setDraft((prev) => ({
                  ...prev,
                  sortOrder: event.target.value as InvoicesListFilters["sortOrder"],
                }))
              }
            >
              <option value="desc">Absteigend</option>
              <option value="asc">Aufsteigend</option>
            </select>
          </div>

          <div className="flex items-end gap-2 md:col-span-2 xl:col-span-4">
            <Button type="button" onClick={applyFilters}>Filter anwenden</Button>
            <Button type="button" variant="outline" onClick={resetFilters}>Zurücksetzen</Button>
            <span className="text-sm text-muted-foreground">{totalCount} Rechnungen</span>
          </div>
        </CardContent>
      </Card>

      {invoices.isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
        </div>
      ) : invoices.isError ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            Rechnungen konnten nicht geladen werden. Bitte Seite neu laden.
          </CardContent>
        </Card>
      ) : (
        <InvoicesListTable rows={invoices.data?.items ?? []} />
      )}
    </main>
  );
}
