import { Skeleton } from "@/components/ui/skeleton";

export function DashboardKpiSkeletons(): React.JSX.Element {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {Array.from({ length: 4 }).map((_, index) => (
        <div key={index} className="rounded-xl border border-border p-5">
          <Skeleton className="mb-3 h-4 w-28" />
          <Skeleton className="mb-2 h-8 w-20" />
          <Skeleton className="h-4 w-32" />
        </div>
      ))}
    </div>
  );
}

export function DashboardCardSkeleton({ rows = 5 }: { rows?: number }): React.JSX.Element {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, index) => (
        <Skeleton key={index} className="h-9 w-full" />
      ))}
    </div>
  );
}
