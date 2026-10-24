export type NamedUser = {
  first_name?: string | null;
  last_name?: string | null;
  display_name?: string | null;
  username?: string | null;
};

export function userDisplayName(user: NamedUser | null | undefined, fallback = "User") {
  if (!user) return fallback;
  const name = [user.first_name, user.last_name]
    .map((part) => String(part || "").trim())
    .filter(Boolean)
    .join(" ");
  return name || String(user.display_name || "").trim() || user.username || fallback;
}
