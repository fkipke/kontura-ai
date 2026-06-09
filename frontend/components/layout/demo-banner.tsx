import { config } from "@/lib/config";

export function DemoBanner(): React.JSX.Element | null {
  if (!config.demoMode) {
    return null;
  }

  return (
    <div className="border-b border-amber-500/20 bg-amber-500/10 px-4 py-2 text-center text-xs text-amber-700 md:px-6">
      Demo-Modus aktiv · Testdaten werden für Produkt-Demos genutzt
    </div>
  );
}
