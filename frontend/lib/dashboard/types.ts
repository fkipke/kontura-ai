import { z } from "zod";

const decimalSchema = z.union([z.string(), z.number()]);

export const dashboardKpisSchema = z.object({
  open_invoices_count: z.number().int(),
  open_invoices_total_amount: decimalSchema,
  paid_this_month_total: decimalSchema,
  skonto_expiring_soon_count: z.number().int(),
  skonto_expiring_soon_potential_savings: decimalSchema,
  vat_balance_current_quarter: decimalSchema,
});

export const cashflowResponseSchema = z.object({
  points: z.array(
    z.object({
      month: z.string(),
      total_amount: decimalSchema,
      invoice_count: z.number().int(),
    }),
  ),
});

export const topVendorsResponseSchema = z.object({
  vendors: z.array(
    z.object({
      vendor_name: z.string(),
      invoice_count: z.number().int(),
      total_amount: decimalSchema,
    }),
  ),
});

export const dashboardInvoiceStatusSchema = z.enum([
  "received",
  "processing",
  "extracted",
  "reviewed",
  "booked",
]);

export const recentActivityItemSchema = z.object({
  id: z.string().uuid(),
  invoice_number: z.string(),
  vendor_name: z.string(),
  invoice_date: z.string(),
  total_amount: decimalSchema,
  currency: z.string(),
  status: dashboardInvoiceStatusSchema,
  created_at: z.string(),
  updated_at: z.string(),
});

export const alertsResponseSchema = z.object({
  alerts: z.array(
    z.object({
      type: z.enum(["unusual_amount", "first_time_high_value_vendor", "potential_duplicate"]),
      invoice_id: z.string().uuid(),
      invoice_number: z.string().nullable(),
      vendor_name: z.string().nullable(),
      total_amount: decimalSchema.nullable(),
      message: z.string(),
      severity: z.enum(["info", "warning", "danger"]),
    }),
  ),
});

export type DashboardKpis = z.infer<typeof dashboardKpisSchema>;
export type CashflowResponse = z.infer<typeof cashflowResponseSchema>;
export type TopVendorsResponse = z.infer<typeof topVendorsResponseSchema>;
export type RecentActivityItem = z.infer<typeof recentActivityItemSchema>;
export type AlertsResponse = z.infer<typeof alertsResponseSchema>;
export type DashboardInvoiceStatus = z.infer<typeof dashboardInvoiceStatusSchema>;
