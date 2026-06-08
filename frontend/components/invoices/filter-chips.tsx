import { X } from "lucide-react";

import { Button } from "@/components/ui/button";

export interface FilterChip {
  key: string;
  label: string;
  onRemove: () => void;
}

export function FilterChips({ chips }: { chips: FilterChip[] }): React.JSX.Element | null {
  if (chips.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-wrap gap-2">
      {chips.map((chip) => (
        <Button
          key={chip.key}
          variant="outline"
          size="sm"
          type="button"
          className="h-8 rounded-full"
          onClick={chip.onRemove}
        >
          {chip.label}
          <X className="ml-1 h-3.5 w-3.5" aria-hidden />
        </Button>
      ))}
    </div>
  );
}
