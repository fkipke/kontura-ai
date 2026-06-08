"use client";

import { useMemo, useState } from "react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { Check, ChevronDown, Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface VendorDropdownProps {
  vendors: string[];
  value: string;
  onChange: (vendor: string) => void;
}

export function VendorDropdown({ vendors, value, onChange }: VendorDropdownProps): React.JSX.Element {
  const [search, setSearch] = useState("");
  const showSearch = vendors.length > 20;
  const filtered = useMemo(() => {
    if (!showSearch || !search.trim()) {
      return vendors;
    }
    const needle = search.toLowerCase();
    return vendors.filter((vendor) => vendor.toLowerCase().includes(needle));
  }, [vendors, showSearch, search]);

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <Button type="button" variant="outline" className="justify-between">
          {value || "Lieferant"}
          <ChevronDown className="ml-2 h-4 w-4" aria-hidden />
        </Button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="start"
          sideOffset={8}
          className="z-50 min-w-[260px] rounded-lg border border-border bg-background p-1 shadow-lg"
        >
          {showSearch ? (
            <div className="px-1 pb-1">
              <div className="relative">
                <Search className="pointer-events-none absolute left-2 top-2 h-4 w-4 text-muted-foreground" />
                <Input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  className="h-8 pl-8"
                  placeholder="Lieferant suchen…"
                />
              </div>
            </div>
          ) : null}
          <DropdownMenu.Item
            className="flex cursor-pointer items-center justify-between rounded-md px-2 py-2 text-sm outline-none hover:bg-accent"
            onSelect={() => onChange("")}
          >
            <span>Alle Lieferanten</span>
            {!value ? <Check className="h-4 w-4 text-primary" aria-hidden /> : null}
          </DropdownMenu.Item>
          <div className="max-h-56 overflow-y-auto">
            {filtered.map((vendor) => (
              <DropdownMenu.Item
                key={vendor}
                className="flex cursor-pointer items-center justify-between rounded-md px-2 py-2 text-sm outline-none hover:bg-accent"
                onSelect={() => onChange(vendor)}
              >
                <span className="truncate">{vendor}</span>
                {vendor === value ? <Check className="h-4 w-4 text-primary" aria-hidden /> : null}
              </DropdownMenu.Item>
            ))}
          </div>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
