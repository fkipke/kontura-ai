import { AlertTriangle, FileCheck2, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";

export type ExtractionMethod = "xrechnung_ubl" | "xrechnung_cii" | "zugferd_v2" | "ai_vision" | null;
export type ExtendedExtractionMethod =
  | "xrechnung_ubl"
  | "xrechnung_cii"
  | "zugferd_v2"
  | "ai_vision"
  | "not_an_invoice"
  | null;

export type ZugferdProfile =
  | "minimum"
  | "basic_wl"
  | "basic"
  | "en16931"
  | "extended"
  | "xrechnung"
  | null;

interface Props {
  method: ExtendedExtractionMethod;
  zugferdProfile?: ZugferdProfile;
}

const METHOD_CONFIG: Record<
  Exclude<NonNullable<ExtendedExtractionMethod>, "not_an_invoice">,
  {
    label: string;
    variant: "secondary" | "success";
    className: string;
    icon: typeof FileCheck2;
    ariaLabel: string;
  }
> = {
  xrechnung_ubl: {
    label: "XRechnung",
    variant: "success",
    className: "bg-emerald-100 text-emerald-900 border-emerald-300 hover:bg-emerald-100",
    icon: FileCheck2,
    ariaLabel: "Extrahiert aus XRechnung-XML (UBL-Format), 100% Genauigkeit",
  },
  xrechnung_cii: {
    label: "XRechnung",
    variant: "success",
    className: "bg-emerald-100 text-emerald-900 border-emerald-300 hover:bg-emerald-100",
    icon: FileCheck2,
    ariaLabel: "Extrahiert aus XRechnung-XML (CII-Format), 100% Genauigkeit",
  },
  zugferd_v2: {
    label: "ZUGFeRD",
    variant: "success",
    className: "bg-teal-100 text-teal-900 border-teal-300 hover:bg-teal-100",
    icon: FileCheck2,
    ariaLabel: "Extrahiert aus ZUGFeRD-PDF, 100% Genauigkeit",
  },
  ai_vision: {
    label: "KI-extrahiert",
    variant: "secondary",
    className: "bg-blue-100 text-blue-900 border-blue-300 hover:bg-blue-100",
    icon: Sparkles,
    ariaLabel: "Extrahiert per KI-Vision (GPT-4o), bitte Felder prüfen",
  },
};

export function ExtractionMethodBadge({
  method,
  zugferdProfile = null,
}: Props): React.JSX.Element | null {
  if (method === null) {
    return null;
  }

  if (method === "not_an_invoice") {
    return (
      <Badge
        variant="destructive"
        className="inline-flex items-center gap-1.5 rounded-md border border-rose-300 bg-rose-100 px-2.5 py-1 text-xs font-medium text-rose-900 hover:bg-rose-100"
      >
        <AlertTriangle className="h-3.5 w-3.5" aria-hidden />
        <span>Keine Rechnung</span>
      </Badge>
    );
  }

  const config = METHOD_CONFIG[method];
  const Icon = config.icon;
  const showMinimumWarning = method === "zugferd_v2" && zugferdProfile === "minimum";

  return (
    <div className="flex flex-col gap-2">
      <Badge
        variant={config.variant}
        className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium ${config.className}`}
        aria-label={config.ariaLabel}
        title={config.ariaLabel}
      >
        <Icon className="h-3.5 w-3.5" aria-hidden />
        <span>{config.label}</span>
      </Badge>

      {showMinimumWarning ? (
        <Badge
          variant="warning"
          className="inline-flex items-center gap-1.5 rounded-md border border-amber-300 bg-amber-100 px-2.5 py-1 text-xs font-medium text-amber-900 hover:bg-amber-100"
          aria-label="ZUGFeRD-MINIMUM-Profil erkannt. Dieses Profil enthält keine Einzelpositionen. Bitte Buchungspositionen manuell ergänzen oder per KI nachextrahieren."
          title="ZUGFeRD-MINIMUM-Profil erkannt. Dieses Profil enthält keine Einzelpositionen. Bitte Buchungspositionen manuell ergänzen oder per KI nachextrahieren."
        >
          <AlertTriangle className="h-3.5 w-3.5" aria-hidden />
          <span>MINIMUM-Profil — Positionen ggf. ergänzen</span>
        </Badge>
      ) : null}
    </div>
  );
}
