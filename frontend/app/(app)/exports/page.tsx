import { Card, CardContent } from "@/components/ui/card";
import { DatevExportPreview } from "@/components/exports/datev-export-preview";

export const metadata = {
  title: "DATEV-Export",
};

export default function ExportsPage(): React.JSX.Element {
  return (
    <main className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-3xl font-semibold tracking-tight">DATEV-Export</h1>
        <p className="text-sm text-muted-foreground">
          Geprüfte Eingangsrechnungen als EXTF-Buchungsstapel-CSV für DATEV-Rechnungswesen
          exportieren.
        </p>
      </header>

      <Card>
        <CardContent>
          <DatevExportPreview />
        </CardContent>
      </Card>

      <Card>
        <CardContent className="space-y-3">
          <h2 className="text-base font-semibold">Hinweise</h2>
          <ul className="space-y-1.5 text-sm text-muted-foreground">
            <li>
              Es werden ausschließlich als{" "}
              <strong className="text-foreground">geprüft markierte</strong> Rechnungen
              exportiert.
            </li>
            <li>
              Der <strong className="text-foreground">BU-Schlüssel</strong> muss in DATEV manuell
              vergeben werden (G4.0-MVP-Beschränkung).
            </li>
            <li>
              Wirtschaftsjahres-Filter:{" "}
              <strong className="text-foreground">
                „Alle Wirtschaftsjahre einschließen“
              </strong>{" "}
              überspringt die Standard-Einschränkung auf das aktuelle Wirtschaftsjahr und
              exportiert alle geprüften Rechnungen im gewählten Zeitraum.
            </li>
            <li>
              Format: EXTF-Buchungsstapel (Windows-1252, Semikolon-getrennt) — direkt importierbar
              in DATEV Rechnungswesen / Unternehmen online.
            </li>
          </ul>
        </CardContent>
      </Card>
    </main>
  );
}
