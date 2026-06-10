"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Calendar, FileText, Filter, Search, X } from "lucide-react";

import { StatusBadge } from "@/components/invoices/status-badge";
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
import { cn } from "@/lib/utils";
import type { InvoiceFile, InvoiceStatus } from "@/lib/api/schemas";

interface InvoiceTableProps {
  rows: InvoiceFile[];
}

// Erkennt synthetisch generierte Test-Dateien (RE-YYYY-NNNN.pdf), die
// haeufig keinen Vendor / kein Datum haben. Wird per Default ausgeblendet
// damit das Demo-Video clean wirkt - kann per Toggle wieder sichtbar gemacht
// werden.
function isLikelyTestFile(row: InvoiceFile): boolean {
  const isGeneratedName = /^RE-\d{4}-\d{4}\.pdf$/i.test(row.filename);
  const hasNoVendor = !row.vendor_name;
  return isGeneratedName && hasNoVendor;
}

function mimeMeta(mime: string): { label: string; tone: string } {
  const lower = mime.toLowerCase();
  if (lower === "application/pdf") {
    return { label: "PDF", tone: "border-rose-500/20 bg-rose-500/5 text-rose-600 dark:text-rose-400" };
  }
  if (lower === "application/xml" || lower === "text/xml") {
    return { label: "XML", tone: "border-emerald-500/20 bg-emerald-500/5 text-emerald-600 dark:text-emerald-400" };
  }
  if (lower === "image/png") {
    return { label: "PNG", tone: "border-blue-500/20 bg-blue-500/5 text-blue-600 dark:text-blue-400" };
  }
  if (lower === "image/jpeg") {
    return { label: "JPG", tone: "border-indigo-500/20 bg-indigo-500/5 text-indigo-600 dark:text-indigo-400" };
  }
  return { label: "DATEI", tone: "border-border bg-muted text-muted-foreground" };
}

function isToday(iso: string): boolean {
  const d = new Date(iso);
  const now = new Date();
  return (
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()
  );
}

type StatusFilter = "all" | InvoiceStatus;

export function InvoiceTable({ rows }: InvoiceTableProps): React.JSX.Element {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [showTestFiles, setShowTestFiles] = useState(false);

  const hiddenTestCount = useMemo(
    () => rows.filter((r) => isLikelyTestFile(r)).length,
    [rows],
  );

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return rows
      .filter((r) => (showTestFiles ? true : !isLikelyTestFile(r)))
      .filter((r) => (statusFilter === "all" ? true : r.extraction_status === statusFilter))
      .filter((r) => {
        if (!needle) return true;
        const haystacks = [
          r.filename,
          r.vendor_name ?? "",
          r.currency ?? "",
          r.total_amount != null ? String(r.total_amount) : "",
        ];
        return haystacks.some((h) => h.toLowerCase().includes(needle));
      })
      .sort((a, b) => b.created_at.localeCompare(a.created_at));
  }, [rows, query, statusFilter, showTestFiles]);

  // Komplett leerer Datenbestand
  if (rows.length === 0) {
    return (
      <Card>
        <CardContent className="space-y-2 py-10 text-center">
          <p className="text-sm font-medium">Noch keine Rechnungen hochgeladen.</p>
          <p className="text-sm text-muted-foreground">
            Ziehe eine PDF hierher oder klicke oben.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      {/* Toolbar: Suche + Status-Filter + Test-Daten-Toggle */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-1 items-center gap-2">
          <div className="relative flex-1 sm:max-w-md">
            <Search
              className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden
            />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Lieferant oder Dateiname suchen…"
              className="w-full rounded-md border border-input bg-background py-2 pl-8 pr-8 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
            {query && (
              <button
                type="button"
                onClick={() => setQuery("")}
                aria-label="Suche zurücksetzen"
                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                <X className="h-4 w-4" aria-hidden />
              </button>
            )}
          </div>
          <div className="relative">
            <Filter
              className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden
            />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
              className="appearance-none rounded-md border border-input bg-background py-2 pl-8 pr-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="all">Alle Status</option>
              <option value="completed">Nur fertig</option>
              <option value="processing">In Bearbeitung</option>
              <option value="pending">Wartend</option>
              <option value="failed">Fehlgeschlagen</option>
            </select>
          </div>
        </div>
        {hiddenTestCount > 0 && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setShowTestFiles((prev) => !prev)}
            className="text-xs text-muted-foreground"
          >
            {showTestFiles
              ? `Testdateien ausblenden (${hiddenTestCount})`
              : `Testdateien anzeigen (${hiddenTestCount})`}
          </Button>
        )}
      </div>

      {filtered.length === 0 ? (
        <Card>
          <CardContent className="space-y-1 py-10 text-center">
            <p className="text-sm font-medium">Keine Treffer.</p>
            <p className="text-xs text-muted-foreground">
              Suche oder Filter anpassen, um weitere Einträge zu sehen.
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[110px]">Status</TableHead>
                  <TableHead className="w-[80px]">Typ</TableHead>
                  <TableHead>Dateiname</TableHead>
                  <TableHead>Lieferant</TableHead>
                  <TableHead>Datum</TableHead>
                  <TableHead className="text-right">Betrag</TableHead>
                  <TableHead>Hochgeladen</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((row) => {
                  const mime = mimeMeta(row.mime_type);
                  const fresh = isToday(row.created_at);
                  return (
                    <TableRow
                      key={row.id}
                      className="cursor-pointer transition-colors"
                      onClick={() => router.push(`/invoices/${row.id}`)}
                    >
                      <TableCell>
                        <StatusBadge status={row.extraction_status} />
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant="secondary"
                          className={cn(
                            "gap-1 font-mono text-[10px] tracking-wide uppercase",
                            mime.tone,
                          )}
                        >
                          <FileText className="h-3 w-3" aria-hidden />
                          {mime.label}
                        </Badge>
                      </TableCell>
                      <TableCell className="max-w-[280px] truncate font-medium">
                        {row.filename}
                      </TableCell>
                      <TableCell>
                        {row.extraction_status === "pending" ||
                        row.extraction_status === "processing" ? (
                          <Skeleton className="h-4 w-28" />
                        ) : row.extraction_status === "completed" ? (
                          (row.vendor_name ?? "–")
                        ) : (
                          "—"
                        )}
                      </TableCell>
                      <TableCell>
                        {row.extraction_status === "completed"
                          ? formatGermanDate(row.invoice_date ?? null)
                          : "—"}
                      </TableCell>
                      <TableCell className="text-right font-tnum">
                        {row.extraction_status === "completed"
                          ? formatCurrency(row.total_amount ?? null)
                          : row.extraction_status === "pending" ||
                              row.extraction_status === "processing"
                            ? "…"
                            : "—"}
                      </TableCell>
                      <TableCell>
                        <span className="inline-flex items-center gap-1.5 text-sm">
                          {fresh && (
                            <Calendar
                              className="h-3.5 w-3.5 text-emerald-500"
                              aria-hidden
                            />
                          )}
                          <span>
                            {fresh ? "heute" : formatGermanDate(row.created_at)}
                          </span>
                        </span>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
