import {
  useMutation,
  useQueries,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { ApiClientError, apiRequest } from "@/lib/api/client";
import {
  extractionStatusSchema,
  invoiceFileSchema,
  type ExtractionStatus,
  type InvoiceFile,
} from "@/lib/api/schemas";

export interface InvoiceListResult {
  items: InvoiceFile[];
  totalCount: number;
}

async function fetchJsonWithRetry<T>(
  path: string,
  parser: (value: unknown) => T,
): Promise<T> {
  const execute = async (): Promise<T> =>
    apiRequest(
      `/api/proxy${path}`,
      {
        method: "GET",
      },
      parser,
    );

  try {
    return await execute();
  } catch (error) {
    if (error instanceof ApiClientError && error.status === 500) {
      return execute();
    }
    throw error;
  }
}

export function useInvoiceFiles() {
  return useQuery({
    queryKey: ["invoice-files"],
    queryFn: async (): Promise<InvoiceListResult> => {
      const response = await fetch("/api/proxy/api/v1/invoice-files?limit=200&offset=0", {
        method: "GET",
      });

      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as {
          detail?: string;
          status?: number;
          request_id?: string;
          errors?: Array<Record<string, unknown>>;
        } | null;
        throw new ApiClientError(
          response.status,
          payload?.detail ?? "Liste konnte nicht geladen werden.",
          payload?.request_id ?? null,
          payload?.errors ?? [],
          null,
        );
      }

      const body = (await response.json()) as unknown;
      // Schema-Parse mit safeParse damit wir bei kaputten Datensaetzen NICHT
      // die ganze Liste verlieren - kaputte Items werden geloggt + weggefiltert.
      const parsedItems: InvoiceFile[] = [];
      if (Array.isArray(body)) {
        for (const item of body) {
          const result = invoiceFileSchema.safeParse(item);
          if (result.success) {
            parsedItems.push(result.data);
          } else {
            // eslint-disable-next-line no-console
            console.warn(
              "[invoice-files] Skipping malformed item:",
              result.error.issues,
              item,
            );
          }
        }
      } else {
        // eslint-disable-next-line no-console
        console.error("[invoice-files] API did not return an array:", body);
      }

      const totalRaw = response.headers.get("x-total-count");
      const totalCount = totalRaw ? Number.parseInt(totalRaw, 10) : parsedItems.length;

      return {
        items: parsedItems,
        totalCount,
      };
    },
    // Immer beim Page-Mount frisch holen + Cache aggressiv eviciten -
    // vermeidet "leere Liste" nach Navigation/Upload.
    refetchOnMount: "always",
    refetchOnWindowFocus: true,
    staleTime: 0,
    gcTime: 0,
    refetchInterval: (query) => {
      const list = query.state.data?.items ?? [];
      const hasActive = list.some(
        (item) =>
          item.extraction_status === "pending" ||
          item.extraction_status === "processing",
      );
      return hasActive ? 3000 : false;
    },
  });
}

export function useExtractionStatuses(ids: string[]) {
  return useQueries({
    queries: ids.map((id) => ({
      queryKey: ["extraction", id],
      queryFn: () =>
        fetchJsonWithRetry(`/api/v1/invoice-files/${id}/extraction`, (value) =>
          extractionStatusSchema.parse(value),
        ),
      staleTime: 0,
      retry: 1,
    })),
  });
}

export function useInvoiceFile(id: string) {
  return useQuery({
    queryKey: ["invoice-file", id],
    queryFn: () =>
      apiRequest(
        `/api/proxy/api/v1/invoice-files?limit=1&offset=0`,
        { method: "GET" },
        (value) => invoiceFileSchema.array().parse(value),
      ).then((items) => items.find((item) => item.id === id) ?? null),
  });
}

export function useExtractionStatus(id: string) {
  return useQuery({
    queryKey: ["extraction", id],
    queryFn: () =>
      fetchJsonWithRetry(`/api/v1/invoice-files/${id}/extraction`, (value) =>
        extractionStatusSchema.parse(value),
      ),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "pending" || status === "processing") {
        return 2000;
      }
      return false;
    },
    retry: 1,
  });
}

export function useUploadInvoice() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch("/api/proxy/api/v1/invoice-files", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as {
          detail?: string;
          status?: number;
          request_id?: string;
          errors?: Array<Record<string, unknown>>;
        } | null;
        throw new ApiClientError(
          response.status,
          payload?.detail ?? "Upload fehlgeschlagen.",
          payload?.request_id ?? null,
          payload?.errors ?? [],
          null,
        );
      }

      const body = invoiceFileSchema.parse((await response.json()) as unknown);
      return {
        item: body,
        deduplicatedHeader: response.headers.get("x-deduplicated") === "true",
      };
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["invoice-files"] });
      await queryClient.refetchQueries({ queryKey: ["invoice-files"] });
      // Dashboard-Karten ebenfalls aktualisieren
      await queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useTriggerExtraction(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (): Promise<ExtractionStatus> => {
      const execute = async (): Promise<ExtractionStatus> =>
        apiRequest(
          `/api/proxy/api/v1/invoice-files/${id}/extract?force=true`,
          { method: "POST" },
          (value) => extractionStatusSchema.parse(value),
        );

      try {
        return await execute();
      } catch (error) {
        if (error instanceof ApiClientError && error.status === 500) {
          return execute();
        }
        throw error;
      }
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["invoice-files"] });
      await queryClient.invalidateQueries({ queryKey: ["extraction", id] });
    },
  });
}

export async function fetchInvoiceFileBlob(id: string): Promise<Blob> {
  const response = await fetch(`/api/proxy/api/v1/invoice-files/${id}`, {
    method: "GET",
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as {
      detail?: string;
      status?: number;
      request_id?: string;
      errors?: Array<Record<string, unknown>>;
    } | null;
    throw new ApiClientError(
      response.status,
      payload?.detail ?? "PDF konnte nicht geladen werden.",
      payload?.request_id ?? null,
      payload?.errors ?? [],
      null,
    );
  }

  return response.blob();
}
