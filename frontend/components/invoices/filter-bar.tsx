"use client";

import { useEffect, useMemo, useState } from "react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { Check, ChevronDown } from "lucide-react";

import { FilterChips, type FilterChip } from "@/components/invoices/filter-chips";
import { SortDropdown } from "@/components/invoices/sort-dropdown";
import { VendorDropdown } from "@/components/invoices/vendor-dropdown";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { InvoiceFilters } from "@/lib/invoices/url-state";

const STATUS_OPTIONS = [
  { value: "received", label: "Eingegangen" },
  { value: "processing", label: "In Bearbeitung" },
  { value: "extracted", label: "Extrahiert" },
  { value: "reviewed", label: "Geprüft" },
  { value: "booked", label: "Verbucht" },
] as const;

const METHOD_OPTIONS = [
  { value: "", label: "Alle Methoden" },
  { value: "ai_vision", label: "KI-Vision" },
  { value: "xrechnung_ubl", label: "XRechnung UBL" },
  { value: "xrechnung_cii", label: "XRechnung CII" },
  { value: "zugferd_v2", label: "ZUGFeRD" },
  { value: "not_an_invoice", label: "Keine Rechnung" },
] as const;

interface FilterBarProps {
  filters: InvoiceFilters;
  vendors: string[];
  onSetFilter: <K extends keyof InvoiceFilters>(key: K, value: InvoiceFilters[K] | null) => void;
  onReset: () => void;
}

export function InvoiceFilterBar({ filters, vendors, onSetFilter, onReset }: FilterBarProps): React.JSX.Element {
  const [searchInput, setSearchInput] = useState(filters.q);
  const deferredSearch = useMemo(() => searchInput.trim(), [searchInput]);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      if (deferredSearch !== filters.q) {
        onSetFilter("q", deferredSearch);
      }
    }, 300);
    return () => window.clearTimeout(timeout);
  }, [deferredSearch, filters.q, onSetFilter]);

  const chips: FilterChip[] = [];
  if (filters.q) {
    chips.push({ key: "q", label: `Suche: ${filters.q}`, onRemove: () => onSetFilter("q", "") });
  }
  filters.status.forEach((status) => {
    const label = STATUS_OPTIONS.find((option) => option.value === status)?.label ?? status;
    chips.push({
      key: `status-${status}`,
      label: `Status: ${label}`,
      onRemove: () => onSetFilter("status", filters.status.filter((entry) => entry !== status)),
    });
  });
  if (filters.reviewed) {
    chips.push({ key: "reviewed", label: "Nur ungeprüft", onRemove: () => onSetFilter("reviewed", false) });
  }
  if (filters.vendor) {
    chips.push({ key: "vendor", label: `Lieferant: ${filters.vendor}`, onRemove: () => onSetFilter("vendor", "") });
  }
  if (filters.extractionMethod) {
    const label = METHOD_OPTIONS.find((option) => option.value === filters.extractionMethod)?.label ?? filters.extractionMethod;
    chips.push({ key: "method", label: `Methode: ${label}`, onRemove: () => onSetFilter("extractionMethod", "") });
  }
  if (filters.dateFrom || filters.dateTo) {
    chips.push({
      key: "date",
      label: `Datum: ${filters.dateFrom || "…"} bis ${filters.dateTo || "…"}`,
      onRemove: () => {
        onSetFilter("dateFrom", "");
        onSetFilter("dateTo", "");
      },
    });
  }
  if (filters.amountMin || filters.amountMax) {
    chips.push({
      key: "amount",
      label: `Betrag: ${filters.amountMin || "…"} bis ${filters.amountMax || "…"}`,
      onRemove: () => {
        onSetFilter("amountMin", "");
        onSetFilter("amountMax", "");
      },
    });
  }

  const toggleStatus = (status: string): void => {
    if (filters.status.includes(status)) {
      onSetFilter(
        "status",
        filters.status.filter((entry) => entry !== status),
      );
      return;
    }
    onSetFilter("status", [...filters.status, status]);
  };

  return (
    <div className="space-y-3 rounded-xl border border-border bg-card p-4">
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[1fr_auto]">
        <Input
          value={searchInput}
          onChange={(event) => setSearchInput(event.target.value)}
          placeholder="Rechnungsnummer, Lieferant oder Position…"
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              onSetFilter("q", searchInput.trim());
            }
          }}
        />
        <SortDropdown value={filters.sort} onChange={(sort) => onSetFilter("sort", sort)} />
      </div>

      <FilterChips chips={chips} />

      <div className="flex flex-wrap gap-2">
        <DropdownMenu.Root>
          <DropdownMenu.Trigger asChild>
            <Button type="button" variant="outline">
              Status
              <ChevronDown className="ml-2 h-4 w-4" aria-hidden />
            </Button>
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content
              align="start"
              sideOffset={8}
              className="z-50 min-w-[220px] rounded-lg border border-border bg-background p-1 shadow-lg"
            >
              {STATUS_OPTIONS.map((option) => (
                <DropdownMenu.CheckboxItem
                  key={option.value}
                  checked={filters.status.includes(option.value)}
                  className="flex cursor-pointer items-center justify-between rounded-md px-2 py-2 text-sm outline-none hover:bg-accent"
                  onCheckedChange={() => toggleStatus(option.value)}
                >
                  <span>{option.label}</span>
                  {filters.status.includes(option.value) ? <Check className="h-4 w-4 text-primary" aria-hidden /> : null}
                </DropdownMenu.CheckboxItem>
              ))}
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>

        <Button
          type="button"
          variant={filters.reviewed ? "default" : "outline"}
          onClick={() => onSetFilter("reviewed", !filters.reviewed)}
        >
          Nur ungeprüft
        </Button>

        <VendorDropdown vendors={vendors} value={filters.vendor} onChange={(vendor) => onSetFilter("vendor", vendor)} />

        <DropdownMenu.Root>
          <DropdownMenu.Trigger asChild>
            <Button type="button" variant="outline">
              {METHOD_OPTIONS.find((option) => option.value === filters.extractionMethod)?.label ?? "Methode"}
              <ChevronDown className="ml-2 h-4 w-4" aria-hidden />
            </Button>
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content
              align="start"
              sideOffset={8}
              className="z-50 min-w-[220px] rounded-lg border border-border bg-background p-1 shadow-lg"
            >
              {METHOD_OPTIONS.map((option) => (
                <DropdownMenu.Item
                  key={option.value || "all"}
                  className="flex cursor-pointer items-center justify-between rounded-md px-2 py-2 text-sm outline-none hover:bg-accent"
                  onSelect={() => onSetFilter("extractionMethod", option.value)}
                >
                  <span>{option.label}</span>
                  {filters.extractionMethod === option.value ? <Check className="h-4 w-4 text-primary" aria-hidden /> : null}
                </DropdownMenu.Item>
              ))}
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>

        <Input
          type="date"
          value={filters.dateFrom}
          onChange={(event) => onSetFilter("dateFrom", event.target.value)}
          className="w-[170px]"
        />
        <Input
          type="date"
          value={filters.dateTo}
          onChange={(event) => onSetFilter("dateTo", event.target.value)}
          className="w-[170px]"
        />
        <Input
          type="number"
          value={filters.amountMin}
          placeholder="Betrag min"
          onChange={(event) => onSetFilter("amountMin", event.target.value)}
          className="w-[140px]"
        />
        <Input
          type="number"
          value={filters.amountMax}
          placeholder="Betrag max"
          onChange={(event) => onSetFilter("amountMax", event.target.value)}
          className="w-[140px]"
        />
        <Button
          type="button"
          variant="ghost"
          onClick={() => {
            setSearchInput("");
            onReset();
          }}
        >
          Filter zurücksetzen
        </Button>
      </div>
    </div>
  );
}
