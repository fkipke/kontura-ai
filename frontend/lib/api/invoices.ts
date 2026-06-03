"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";

import { ApiClientError, apiRequest } from "@/lib/api/client";
import {
  invoiceResponseSchema,
  type InvoiceResponse,
  type ValidationWarning,
} from "@/lib/api/schemas";

const invoiceLineItemPayloadSchema = z.object({
  description: z.string().nullable().optional(),
  quantity: z.union([z.string(), z.number()]).nullable().optional(),
  unit_price: z.union([z.string(), z.number()]).nullable().optional(),
  total_price: z.union([z.string(), z.number()]).nullable().optional(),
});

const invoiceUpdatePayloadSchema = z.object({
  expected_version: z.number().int().min(1),
  vendor_name: z.string().nullable().optional(),
  invoice_number: z.string().nullable().optional(),
  invoice_date: z.string().nullable().optional(),
  net_amount: z.string().nullable().optional(),
  tax_amount: z.string().nullable().optional(),
  total_amount: z.string().nullable().optional(),
  currency: z.string().nullable().optional(),
  line_items: z.array(invoiceLineItemPayloadSchema).nullable().optional(),
  creditor_account_number: z.number().int().min(10000).max(999999).nullable().optional(),
  is_reviewed: z.boolean().nullable().optional(),
});

// G3.2: 409-Konflikt-Response (Optimistic Lock)
export interface ConflictResponse {
  detail: string;
  current_version: number;
  current_state: InvoiceResponse;
}

export class InvoiceConflictError extends Error {
  constructor(public readonly conflict: ConflictResponse) {
    super(conflict.detail);
    this.name = "InvoiceConflictError";
  }
}

// G3.2: PATCH-Body — nur gesetzte Felder werden gesendet
export interface InvoiceUpdatePayload {
  expected_version: number;
  vendor_name?: string | null;
  invoice_number?: string | null;
  invoice_date?: string | null;
  net_amount?: string | null;
  tax_amount?: string | null;
  total_amount?: string | null;
  currency?: string | null;
  line_items?: Array<{
    description?: string | null;
    quantity?: string | number | null;
    unit_price?: string | number | null;
    total_price?: string | number | null;
  }> | null;
  creditor_account_number?: number | null;
  is_reviewed?: boolean | null;
}

export function useInvoice(invoiceId: string) {
  return useQuery({
    queryKey: ["invoice", invoiceId],
    queryFn: () =>
      apiRequest(
        `/api/proxy/invoices/${invoiceId}`,
        { method: "GET" },
        (value) => invoiceResponseSchema.parse(value),
      ),
    enabled: Boolean(invoiceId),
  });
}

export function useUpdateInvoice(invoiceId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (
      payload: InvoiceUpdatePayload,
    ): Promise<{ data: InvoiceResponse; warnings: ValidationWarning[] }> => {
      const body = invoiceUpdatePayloadSchema.parse(payload);
      const response = await fetch(`/api/proxy/invoices/${invoiceId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      // 409 Optimistic-Lock-Konflikt: separater Fehler-Typ
      if (response.status === 409) {
        const raw = (await response.json()) as {
          detail: string;
          current_version: number;
          current_state: unknown;
        };
        const conflict: ConflictResponse = {
          detail: raw.detail,
          current_version: raw.current_version,
          current_state: invoiceResponseSchema.parse(raw.current_state),
        };
        throw new InvoiceConflictError(conflict);
      }

      if (!response.ok) {
        const errorPayload = (await response.json().catch(() => null)) as {
          detail?: string;
          status?: number;
          request_id?: string;
          errors?: Array<Record<string, unknown>>;
        } | null;
        throw new ApiClientError(
          response.status,
          errorPayload?.detail ?? "Aktualisierung fehlgeschlagen.",
          errorPayload?.request_id ?? null,
          errorPayload?.errors ?? [],
          null,
        );
      }

      const raw = (await response.json()) as unknown;
      const data = invoiceResponseSchema.parse(raw);
      return { data, warnings: data.validation_warnings };
    },

    onSuccess: async ({ data }) => {
      // Cache aktualisieren mit neuem Stand (inkl. version+1)
      queryClient.setQueryData(["invoice", invoiceId], data);
      await queryClient.invalidateQueries({ queryKey: ["invoice", invoiceId] });
    },
  });
}
