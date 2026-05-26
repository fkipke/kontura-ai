import * as React from "react";

import { cn } from "@/lib/utils";

export function Label(
  props: React.LabelHTMLAttributes<HTMLLabelElement>,
): React.JSX.Element {
  return (
    <label
      {...props}
      className={cn("text-sm font-medium text-foreground", props.className)}
    />
  );
}
