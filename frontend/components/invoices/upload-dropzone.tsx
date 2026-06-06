"use client";

import { Upload } from "lucide-react";
import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { Card, CardContent } from "@/components/ui/card";
import { ApiClientError } from "@/lib/api/client";
import { useUploadInvoice } from "@/lib/api/invoiceFiles";

const ALLOWED_TYPES = [
  "application/pdf",
  "image/png",
  "image/jpeg",
  "application/xml",
  "text/xml",
];
const MAX_SIZE_BYTES = 10 * 1024 * 1024;

export function UploadDropzone(): React.JSX.Element {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [active, setActive] = useState(false);
  const uploadMutation = useUploadInvoice();

  async function submitFile(file: File): Promise<void> {
    if (!ALLOWED_TYPES.includes(file.type)) {
      toast.error("Nur PDF, PNG, JPEG oder XML sind erlaubt.");
      return;
    }
    if (file.size > MAX_SIZE_BYTES) {
      toast.error("Die Datei ist größer als 10 MB.");
      return;
    }

    try {
      const result = await uploadMutation.mutateAsync(file);
      if (result.deduplicatedHeader || result.item.deduplicated) {
        toast.info("Diese Rechnung war bereits vorhanden — öffne den bestehenden Eintrag.");
        router.push(`/invoices/${result.item.id}`);
        return;
      }
      toast.success("Rechnung hochgeladen. Extraktion läuft…");
    } catch (error) {
      if (error instanceof ApiClientError) {
        toast.error(error.detail);
        return;
      }
      toast.error("Upload fehlgeschlagen.");
    }
  }

  return (
    <Card>
      <CardContent
        className={`flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border border-dashed p-8 text-center transition-colors ${active ? "border-primary bg-primary/5" : "border-border"}`}
        onDragOver={(event) => {
          event.preventDefault();
          setActive(true);
        }}
        onDragLeave={() => setActive(false)}
        onDrop={(event) => {
          event.preventDefault();
          setActive(false);
          const file = event.dataTransfer.files.item(0);
          if (file) {
            void submitFile(file);
          }
        }}
        onClick={() => inputRef.current?.click()}
      >
        <Upload className="h-7 w-7 text-muted-foreground" aria-hidden />
        <div className="space-y-1">
          <p className="text-sm font-medium">PDF, PNG, JPEG oder XML hier ablegen</p>
          <p className="text-xs text-muted-foreground">oder klicken, um eine Datei auszuwählen (max. 10 MB)</p>
        </div>
        {uploadMutation.isPending && (
          <div className="h-2 w-full max-w-sm rounded-full bg-muted">
            <div className="h-2 w-full animate-pulse rounded-full bg-primary" />
          </div>
        )}
        <input
          ref={inputRef}
          type="file"
          className="hidden"
          accept="application/pdf,image/png,image/jpeg,application/xml,text/xml,.xml"
          onChange={(event) => {
            const file = event.target.files?.item(0);
            if (file) {
              void submitFile(file);
            }
            event.target.value = "";
          }}
        />
      </CardContent>
    </Card>
  );
}
