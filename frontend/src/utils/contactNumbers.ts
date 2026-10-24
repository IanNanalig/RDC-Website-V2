export type ContactNumberField = "contact_number" | "phone_number";

const numberRules: Record<ContactNumberField, { prefix: string; length: number; placeholder: string }> = {
  contact_number: { prefix: "02", length: 10, placeholder: "02 xxxx xxxx" },
  phone_number: { prefix: "09", length: 11, placeholder: "09xx xxx xxxx" },
};

export function sanitizeContactNumber(value: string, field: ContactNumberField): string {
  return value.replace(/\D/g, "").slice(0, numberRules[field].length);
}

export function formatContactNumber(value: string, field: ContactNumberField): string {
  const digits = sanitizeContactNumber(value, field);
  if (field === "contact_number") {
    if (digits.length <= 2) return digits;
    if (digits.length <= 6) return `${digits.slice(0, 2)} ${digits.slice(2)}`;
    return `${digits.slice(0, 2)} ${digits.slice(2, 6)} ${digits.slice(6)}`;
  }
  if (digits.length <= 4) return digits;
  if (digits.length <= 7) return `${digits.slice(0, 4)} ${digits.slice(4)}`;
  return `${digits.slice(0, 4)} ${digits.slice(4, 7)} ${digits.slice(7)}`;
}

export function contactNumberError(value: string, field: ContactNumberField): string {
  const digits = sanitizeContactNumber(value, field);
  const rule = numberRules[field];
  const isValid = field === "contact_number"
    ? /^02\d{8}$/.test(digits)
    : /^09\d{9}$/.test(digits);
  return isValid ? "" : `Enter a valid number: ${rule.placeholder}`;
}
