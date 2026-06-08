const EUR_FORMATTER = new Intl.NumberFormat("de-DE", {
  style: "currency",
  currency: "EUR",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function formatCurrency(value: string | number | null | undefined): string {
  if (value == null) {
    return "–";
  }
  const num = typeof value === "string" ? parseFloat(value) : value;
  if (Number.isNaN(num)) {
    return "–";
  }
  return EUR_FORMATTER.format(num);
}

export function formatGermanDate(input: string | null | undefined): string {
  if (!input) {
    return "–";
  }

  const date = new Date(input);
  if (Number.isNaN(date.getTime())) {
    return "–";
  }

  return new Intl.DateTimeFormat("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(date);
}

export function formatGermanDateTime(input: string | null | undefined): string {
  if (!input) {
    return "–";
  }

  const date = new Date(input);
  if (Number.isNaN(date.getTime())) {
    return "–";
  }

  return new Intl.DateTimeFormat("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function formatRelativeTime(input: string | null | undefined): string {
  if (!input) {
    return "–";
  }

  const date = new Date(input);
  if (Number.isNaN(date.getTime())) {
    return "–";
  }

  const now = Date.now();
  const diffMs = Math.max(0, now - date.getTime());
  const diffSeconds = Math.floor(diffMs / 1000);

  if (diffSeconds < 60) {
    return "gerade eben";
  }

  const diffMinutes = Math.floor(diffSeconds / 60);
  if (diffMinutes < 60) {
    return `vor ${diffMinutes} Min`;
  }

  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) {
    return `vor ${diffHours} Std`;
  }

  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) {
    return `vor ${diffDays} Tagen`;
  }

  return new Intl.DateTimeFormat("de-DE", {
    day: "numeric",
    month: "short",
  }).format(date);
}
