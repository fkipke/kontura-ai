import { ReactNode } from "react";

interface ViewerToolbarProps {
  filename: string;
  controls: ReactNode;
}

export function ViewerToolbar({ filename, controls }: ViewerToolbarProps): React.JSX.Element {
  return (
    <div className="flex items-center justify-between border-b pb-2">
      <span className="truncate text-xs text-muted-foreground">{filename}</span>
      <div className="flex items-center gap-1">{controls}</div>
    </div>
  );
}
