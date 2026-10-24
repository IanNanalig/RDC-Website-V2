export type PersonNamePart = "first_name" | "last_name";

export function personNameError(value: string, field: PersonNamePart) {
  const label = field === "first_name" ? "First name" : "Last name";
  const trimmed = value.trim();
  if (!trimmed) return `${label} is required`;
  if (trimmed.length > 150) return `${label} must be 150 characters or fewer`;
  if (!/^[\p{L} '-]+$/u.test(trimmed) || !/\p{L}/u.test(trimmed)) {
    return `${label} may contain letters, spaces, apostrophes, and hyphens only`;
  }
  return "";
}
