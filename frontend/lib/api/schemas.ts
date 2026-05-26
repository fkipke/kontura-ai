import { z } from "zod";

export const problemDetailSchema = z.object({
  type: z.string().optional(),
  title: z.string(),
  status: z.number(),
  detail: z.string().optional(),
  instance: z.string().optional(),
  request_id: z.string().optional(),
  errors: z.array(z.record(z.string(), z.unknown())).optional(),
});

export const tokenResponseSchema = z.object({
  access_token: z.string(),
  token_type: z.string(),
  expires_in_seconds: z.number().int().positive(),
});

export const loginPayloadSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
  tenant_slug: z.string().min(2),
});

export const registerPayloadSchema = z.object({
  email: z.string().email(),
  password: z.string().min(12),
  tenant_slug: z.string().min(2),
  tenant_display_name: z.string().min(1),
});

export const meResponseSchema = z.object({
  user_id: z.string(),
  tenant_id: z.string(),
  email: z.string().email(),
  token_expires_at: z.number(),
});

export const invoiceStatusSchema = z.enum([
  "pending",
  "processing",
  "completed",
  "failed",
]);

export const invoiceFileSchema = z.object({
  id: z.string().uuid(),
  filename: z.string(),
  mime_type: z.string(),
  size_bytes: z.number(),
  sha256: z.string(),
  created_at: z.string(),
  deduplicated: z.boolean().optional(),
  extraction_status: invoiceStatusSchema,
});

export const extractionLineItemSchema = z.object({
  description: z.string().nullish(),
  quantity: z.number().nullish(),
  unit_price: z.number().nullish(),
  total_price: z.number().nullish(),
});

export const extractionResultSchema = z.object({
  invoice_number: z.string().nullish(),
  invoice_date: z.string().nullish(),
  due_date: z.string().nullish(),
  vendor_name: z.string().nullish(),
  vendor_address: z.string().nullish(),
  net_amount: z.number().nullish(),
  tax_amount: z.number().nullish(),
  total_amount: z.number().nullish(),
  currency: z.string().nullish(),
  line_items: z.array(extractionLineItemSchema).nullish(),
  confidence_notes: z.string().nullish(),
});

export const extractionStatusSchema = z.object({
  file_id: z.string().uuid(),
  status: invoiceStatusSchema,
  attempts: z.number().int(),
  extracted_at: z.string().nullable(),
  error: z.string().nullable(),
  result: extractionResultSchema.nullish(),
  linked_invoice_id: z.string().uuid().nullable(),
});

export type ProblemDetail = z.infer<typeof problemDetailSchema>;
export type LoginPayload = z.infer<typeof loginPayloadSchema>;
export type RegisterPayload = z.infer<typeof registerPayloadSchema>;
export type InvoiceFile = z.infer<typeof invoiceFileSchema>;
export type ExtractionStatus = z.infer<typeof extractionStatusSchema>;
export type InvoiceStatus = z.infer<typeof invoiceStatusSchema>;
export type MeResponse = z.infer<typeof meResponseSchema>;
