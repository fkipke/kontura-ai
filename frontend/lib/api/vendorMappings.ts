"use client";

import { useQuery } from "@tanstack/react-query";
import { z } from "zod";

import { apiRequest } from "@/lib/api/client";

export const mappingSuggestionSchema = z.object({
  creditor_account_number: z.number().int(),
  vendor_name_raw: z.string(),
  usage_count: z.number().int(),
  last_used_at: z.string(),
  confidence: z.number().min(0).max(1),
  match_type: z.enum(["exact", "fuzzy"]),
  auto_apply: z.boolean(),
});

export type MappingSuggestion = z.infer<typeof mappingSuggestionSchema>;

export function useVendorMappingSuggestion(vendorName: string | null) {
  return useQuery({
    queryKey: ["vendor-mapping-suggest", vendorName],
    queryFn: () =>
      apiRequest(
        `/api/proxy/api/v1/vendor-mappings/suggest?vendor_name=${encodeURIComponent(vendorName ?? "")}`,
        { method: "GET" },
        (value) => mappingSuggestionSchema.nullable().parse(value),
      ),
    enabled: Boolean(vendorName) && (vendorName?.length ?? 0) > 0,
  });
}
