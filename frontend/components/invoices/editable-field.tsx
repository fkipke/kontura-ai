"use client";

import { useEffect, useRef, useState } from "react";
import { Pencil } from "lucide-react";

interface EditableFieldProps {
  /** Aktueller Wert des Feldes (null = leer) */
  value: string | null | undefined;
  /** Anzeige-Label fuer Screen-Reader / Tooltip */
  label: string;
  /** Wird aufgerufen wenn Nutzer speichert (Enter oder Blur) */
  onSave: (newValue: string) => void | Promise<void>;
  /** Laeuft eine Mutation gerade? */
  isPending?: boolean;
  /** Fehlermeldung aus letztem Speicherversuch */
  error?: string | null;
  /** Wurde dieses Feld manuell überschrieben (unterscheidet sich vom KI-Original)? */
  isModified?: boolean;
  /** Typ des Eingabefelds (Standard: text) */
  inputType?: "text" | "date" | "number";
  /** Zahlen-Ausrichtung rechts */
  alignRight?: boolean;
}

/**
 * EditableField: Inline-Edit-Komponente fuer Rechnungsfelder.
 *
 * Hover → Edit-Icon sichtbar.
 * Klick → Input erscheint, fokussiert.
 * Enter → Speichern (onSave aufgerufen).
 * Escape → Verwerfen, alten Wert wiederherstellen.
 * isModified → Blauer Dot als „Manuell korrigiert"-Indikator.
 */
export function EditableField({
  value,
  label,
  onSave,
  isPending = false,
  error = null,
  isModified = false,
  inputType = "text",
  alignRight = false,
}: EditableFieldProps): React.JSX.Element {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value ?? "");
  const inputRef = useRef<HTMLInputElement>(null);

  // Fokus wenn Edit-Modus startet
  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editing]);

  const startEdit = () => {
    setDraft(value ?? "");
    setEditing(true);
  };

  const cancelEdit = () => {
    setDraft(value ?? "");
    setEditing(false);
  };

  const commitEdit = async () => {
    if (draft === (value ?? "")) {
      // Kein Unterschied — nicht speichern
      setEditing(false);
      return;
    }
    await onSave(draft);
    setEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      void commitEdit();
    } else if (e.key === "Escape") {
      e.preventDefault();
      cancelEdit();
    }
  };

  if (editing) {
    return (
      <div className="relative w-full">
        <input
          ref={inputRef}
          type={inputType}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={() => void commitEdit()}
          disabled={isPending}
          aria-label={`${label} bearbeiten`}
          className={[
            "w-full rounded border border-primary bg-background px-2 py-0.5",
            "text-sm outline-none focus:ring-1 focus:ring-primary",
            alignRight ? "text-right font-tnum" : "",
            isPending ? "opacity-50" : "",
          ]
            .filter(Boolean)
            .join(" ")}
        />
        {error && <p className="mt-0.5 text-xs text-destructive">{error}</p>}
      </div>
    );
  }

  const displayValue = value ? value : "–";

  return (
    <button
      type="button"
      onClick={startEdit}
      title={`${label} bearbeiten`}
      aria-label={`${label} bearbeiten`}
      className={[
        "group relative flex w-full cursor-text items-center gap-1 rounded",
        "hover:bg-muted/50 focus-visible:outline focus-visible:outline-2",
        "focus-visible:outline-primary px-1 py-0.5 text-sm transition-colors",
        alignRight ? "justify-end" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {/* Blauer Dot: Feld wurde manuell korrigiert */}
      {isModified && (
        <span
          className="absolute left-0 top-1/2 h-1.5 w-1.5 -translate-x-2 -translate-y-1/2 rounded-full bg-primary"
          title="Manuell korrigiert"
          aria-label="Manuell korrigiert"
        />
      )}
      <span className={value ? "text-foreground" : "text-muted-foreground"}>{displayValue}</span>
      <Pencil
        className="h-3 w-3 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100"
        aria-hidden
      />
    </button>
  );
}
