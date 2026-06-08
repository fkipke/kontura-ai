import { Button } from "@/components/ui/button";

interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
}

export function InvoicePagination({
  page,
  pageSize,
  total,
  totalPages,
  onPageChange,
  onPageSizeChange,
}: PaginationProps): React.JSX.Element {
  return (
    <div className="flex flex-col gap-3 border-t border-border pt-4 md:flex-row md:items-center md:justify-between">
      <div className="text-sm text-muted-foreground">
        Seite {page} von {totalPages} · {total} Treffer
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <select
          className="h-9 rounded-lg border border-border bg-background px-3 text-sm"
          value={pageSize}
          onChange={(event) => onPageSizeChange(Number(event.target.value))}
        >
          <option value={25}>25 / Seite</option>
          <option value={50}>50 / Seite</option>
          <option value={100}>100 / Seite</option>
        </select>
        <Button type="button" variant="outline" size="sm" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
          Zurück
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
        >
          Weiter
        </Button>
      </div>
    </div>
  );
}
