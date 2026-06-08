import { z } from "zod";

export const problemDetailSchema = z.object({
  type: z.string().optional(),
  title: z.string(),
  status: z.number(),
  detail: z.string().optional(),
  instance: z.string().optional(),
  request_id: z.string().optional(),
  code: z.string().optional(),
  errors: z.array(z.record(z.string(), z.unknown())).optional(),
});

export const tokenResponseSchema = z.object({
  access_token: z.string(),
  token_type: z.string(),
  expires_in_seconds: z.number().int().positive(),
});

export const registerResponseSchema = z.object({
  email_verification_required: z.boolean(),
});

export const verifyEmailResponseSchema = z.object({
  verified: z.boolean().optional(),
  already_verified: z.boolean().optional(),
});

export const resendVerificationResponseSchema = z.object({
  sent: z.boolean(),
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
  "not_an_invoice",
]);

export const extractionMethodSchema = z.enum([
  "xrechnung_ubl",
  "xrechnung_cii",
  "zugferd_v2",
  "ai_vision",
  "not_an_invoice",
]).nullable();

export const zugferdProfileSchema = z
  .enum(["minimum", "basic_wl", "basic", "en16931", "extended", "xrechnung"])
  .optional()
  .nullable();

export const invoiceFileSchema = z.object({
  id: z.string().uuid(),
  filename: z.string(),
  mime_type: z.string(),
  size_bytes: z.number(),
  sha256: z.string(),
  created_at: z.string(),
  deduplicated: z.boolean().optional(),
  extraction_status: invoiceStatusSchema,
  // G3.1b: Denormalisierte Extraction-Felder fuer Listings (n+1 vermeiden).
  // Werden nur befuellt, wenn extraction_status == "completed".
  extraction_method: extractionMethodSchema.optional(),
  vendor_name: z.string().nullable().optional(),
  invoice_date: z.string().nullable().optional(),
  total_amount: z.union([z.string(), z.number()]).nullable().optional(),
  currency: z.string().nullable().optional(),
});

export const extractionLineItemSchema = z.object({
  description: z.string().nullish(),
  quantity: z.union([z.string(), z.number()]).nullish(),
  unit_price: z.union([z.string(), z.number()]).nullish(),
  total_price: z.union([z.string(), z.number()]).nullish(),
});

export const extractionResultSchema = z.object({
  invoice_number: z.string().nullish(),
  invoice_date: z.string().nullish(),
  due_date: z.string().nullish(),
  vendor_name: z.string().nullish(),
  vendor_address: z.string().nullish(),
  net_amount: z.union([z.string(), z.number()]).nullish(),
  tax_amount: z.union([z.string(), z.number()]).nullish(),
  total_amount: z.union([z.string(), z.number()]).nullish(),
  currency: z.string().nullish(),
  line_items: z.array(extractionLineItemSchema).nullish(),
  confidence_notes: z.string().nullish(),
  zugferd_profile: zugferdProfileSchema,
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

// G3.2: Invoice-Edit-Schemas

export const validationWarningSchema = z.object({
  code: z.enum(["ust_total_mismatch", "future_invoice_date", "unusual_currency"]),
  message: z.string(),
  field: z.string().nullable().optional(),
});

export const invoiceLineItemSchema = z.object({
  description: z.string().nullable().optional(),
  quantity: z.union([z.string(), z.number()]).nullable().optional(),
  unit_price: z.union([z.string(), z.number()]).nullable().optional(),
  total_price: z.union([z.string(), z.number()]).nullable().optional(),
});

export const invoiceResponseSchema = z.object({
  id: z.string().uuid(),
  tenant_id: z.string(),
  version: z.number().int(),
  is_reviewed: z.boolean(),
  reviewed_at: z.string().nullable(),
  reviewed_by_user_id: z.string().uuid().nullable(),
  vendor_name: z.string().nullable(),
  invoice_number: z.string().nullable(),
  invoice_date: z.string().nullable(),
  net_amount: z.union([z.string(), z.number()]).nullable(),
  tax_amount: z.union([z.string(), z.number()]).nullable(),
  total_amount: z.union([z.string(), z.number()]).nullable(),
  currency: z.string().nullable(),
  line_items: z.array(invoiceLineItemSchema).nullable(),
  status: z.string(),
  created_at: z.string(),
  updated_at: z.string(),
  validation_warnings: z.array(validationWarningSchema),
});

export type ProblemDetail = z.infer<typeof problemDetailSchema>;
export type LoginPayload = z.infer<typeof loginPayloadSchema>;
export type RegisterPayload = z.infer<typeof registerPayloadSchema>;
export type InvoiceFile = z.infer<typeof invoiceFileSchema>;
export type ExtractionStatus = z.infer<typeof extractionStatusSchema>;
export type InvoiceStatus = z.infer<typeof invoiceStatusSchema>;
export type MeResponse = z.infer<typeof meResponseSchema>;
export type RegisterResponse = z.infer<typeof registerResponseSchema>;
export type VerifyEmailResponse = z.infer<typeof verifyEmailResponseSchema>;
export type ResendVerificationResponse = z.infer<typeof resendVerificationResponseSchema>;
// G3.2
export type ValidationWarning = z.infer<typeof validationWarningSchema>;
export type InvoiceLineItem = z.infer<typeof invoiceLineItemSchema>;
export type InvoiceResponse = z.infer<typeof invoiceResponseSchema>;
