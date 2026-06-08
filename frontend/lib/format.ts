const EUR_FORMATTER = new Intl.NumberFormat("de-DE", {
  style: "currency",
  currency: "EUR",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const SECONDS_PER_MINUTE = 60;
const MINUTES_PER_HOUR = 60;
const HOURS_PER_DAY = 24;
const DAYS_PER_WEEK = 7;

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

  if (diffSeconds < SECONDS_PER_MINUTE) {
    return "gerade eben";
  }

  const diffMinutes = Math.floor(diffSeconds / SECONDS_PER_MINUTE);
  if (diffMinutes < MINUTES_PER_HOUR) {
    return `vor ${diffMinutes} Min`;
  }

  const diffHours = Math.floor(diffMinutes / MINUTES_PER_HOUR);
  if (diffHours < HOURS_PER_DAY) {
    return `vor ${diffHours} Std`;
  }

  const diffDays = Math.floor(diffHours / HOURS_PER_DAY);
  if (diffDays < DAYS_PER_WEEK) {
    return `vor ${diffDays} Tagen`;
  }

  return new Intl.DateTimeFormat("de-DE", {
    day: "numeric",
    month: "short",
  }).format(date);
}
