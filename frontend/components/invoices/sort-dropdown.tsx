"use client";

import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { Check, ChevronDown } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { InvoiceSortKey } from "@/lib/invoices/queries";

const SORT_OPTIONS: Array<{ value: InvoiceSortKey; label: string }> = [
  { value: "date_desc", label: "Datum (neueste)" },
  { value: "date_asc", label: "Datum (älteste)" },
  { value: "number_asc", label: "Rechnungsnr. (A-Z)" },
  { value: "number_desc", label: "Rechnungsnr. (Z-A)" },
  { value: "amount_desc", label: "Betrag (höchste)" },
  { value: "amount_asc", label: "Betrag (niedrigste)" },
];

interface SortDropdownProps {
  value: InvoiceSortKey;
  onChange: (next: InvoiceSortKey) => void;
}

export function SortDropdown({ value, onChange }: SortDropdownProps): React.JSX.Element {
  const selected = SORT_OPTIONS.find((option) => option.value === value) ?? SORT_OPTIONS[0];

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <Button type="button" variant="outline" className="justify-between">
          {selected.label}
          <ChevronDown className="ml-2 h-4 w-4" aria-hidden />
        </Button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          sideOffset={8}
          className="z-50 min-w-[220px] rounded-lg border border-border bg-background p-1 shadow-lg"
        >
          {SORT_OPTIONS.map((option) => (
            <DropdownMenu.Item
              key={option.value}
              className="flex cursor-pointer items-center justify-between rounded-md px-2 py-2 text-sm outline-none hover:bg-accent"
              onSelect={() => onChange(option.value)}
            >
              <span>{option.label}</span>
              {option.value === value ? <Check className="h-4 w-4 text-primary" aria-hidden /> : null}
            </DropdownMenu.Item>
          ))}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
