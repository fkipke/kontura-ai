function parseBooleanFlag(value: string | undefined): boolean {
  if (!value) {
    return false;
  }
  return ["1", "true", "yes", "on"].includes(value.trim().toLowerCase());
}

export const config = {
  apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000",
  authCookieName: "kontura_session",
  demoMode: parseBooleanFlag(process.env.NEXT_PUBLIC_DEMO_MODE),
} as const;
