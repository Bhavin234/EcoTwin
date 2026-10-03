/**
 * Consistent formatting for units, currency, percentages, timestamps, and
 * durations (docs Milestone 6, requirement #32). Every number displayed in
 * the app should be formatted through one of these, not ad hoc per
 * component.
 */

const currencyFormatter = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  // Was maximumFractionDigits: 0, which rounded a real, non-zero amount
  // like ₹1.96 down to ₹2 — fine for large sums, misleading for the small
  // amounts this demo dataset actually produces. minimumFractionDigits
  // stays 0 so a whole-rupee amount still displays as "₹1,240", not
  // "₹1,240.00" — decimals only appear when the value actually has them.
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});

const numberFormatter = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 1 });
// Used only for small (<1) quantities where a single decimal place would
// round a real, non-zero value down to a misleading "0" — see formatCo2e.
const smallQuantityFormatter = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 3 });

export function formatCurrency(value) {
  if (value === null || value === undefined) return "—";
  return currencyFormatter.format(value);
}

export function formatConsumption(value, unit) {
  if (value === null || value === undefined) return "—";
  return `${numberFormatter.format(value)} ${unit}`;
}

export function formatCo2e(kg) {
  if (kg === null || kg === undefined) return "—";
  if (kg >= 1000) return `${numberFormatter.format(kg / 1000)} t CO₂e`;
  if (kg > 0 && kg < 1) return `${smallQuantityFormatter.format(kg)} kg CO₂e`;
  return `${numberFormatter.format(kg)} kg CO₂e`;
}

export function formatPercent(value, { signed = false } = {}) {
  if (value === null || value === undefined) return "—";
  const rounded = Math.round(value * 10) / 10;
  const sign = signed && rounded > 0 ? "+" : "";
  return `${sign}${rounded}%`;
}

export function formatTimestamp(isoString) {
  if (!isoString) return "—";
  const date = new Date(isoString);
  return date.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDateOnly(isoString) {
  if (!isoString) return "—";
  const date = new Date(isoString);
  return date.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

export function formatDuration(hours) {
  if (hours === null || hours === undefined) return "—";
  if (hours < 1) return `${Math.round(hours * 60)} min`;
  if (hours < 24) return `${Math.round(hours * 10) / 10} hr${hours >= 2 ? "s" : ""}`;
  const days = Math.round((hours / 24) * 10) / 10;
  return `${days} day${days >= 2 ? "s" : ""}`;
}

export function titleCase(value) {
  if (!value) return "";
  return value
    .toString()
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export const RESOURCE_UNIT = { electricity: "kWh", water: "L" };
