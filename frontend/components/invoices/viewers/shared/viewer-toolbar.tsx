import { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface ViewerToolbarProps {
  filename: string;
  controls: ReactNode;
  className?: string;
}

export function ViewerToolbar({
  filename,
  controls,
  className,
}: ViewerToolbarProps): React.JSX.Element {
  return (
    <div className={cn("flex items-center justify-between border-b pb-2", className)}>
      <span className="truncate text-xs text-muted-foreground">{filename}</span>
      <div className="flex items-center gap-1">{controls}</div>
    </div>
  );
}
