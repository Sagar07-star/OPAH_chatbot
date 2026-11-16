import type { ProposalChange } from "../../types";
import { formatDate, money, titleCase } from "../../services/format";

const MONEY_FIELDS = new Set(["budget", "rate", "price", "total", "subtotal", "fee", "refund_amount"]);
const DATE_FIELDS = new Set(["start_date", "end_date", "deliverables_due_date", "date"]);

export function displayValue(field: string, value: unknown): string {
  if (value === null || value === undefined || value === "") return "Not set";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (Array.isArray(value)) {
    return value.length === 0 ? "None" : value.map((item) => displayValue(field, item)).join(", ");
  }
  if (typeof value === "object") {
    const record = value as Record<string, unknown>;
    if (typeof record.display === "string") return record.display;
    if (typeof record.label === "string") return record.label;
    return Object.entries(record)
      .map(([key, item]) => `${titleCase(key)}: ${String(item)}`)
      .join(", ");
  }
  if (typeof value === "number") {
    if (MONEY_FIELDS.has(field)) return money(value);
    return String(value);
  }
  const text = String(value);
  if (DATE_FIELDS.has(field) && /^\d{4}-\d{2}-\d{2}/.test(text)) return formatDate(text);
  if (MONEY_FIELDS.has(field) && /^\d+$/.test(text)) return money(Number(text));
  if (/^[A-Z0-9_]+$/.test(text)) return titleCase(text);
  return text;
}

export function changeValue(change: ProposalChange): { old: string; next: string } {
  return { old: displayValue(change.field, change.old), next: displayValue(change.field, change.new) };
}
