export type ResolutionLegendEntry = { key?: string; label: string; color: string };

export function resolutionLegendKey(entry: Pick<ResolutionLegendEntry, "key" | "label">) {
  return entry.key || entry.label.trim().toLowerCase();
}

export function findResolutionLegendEntry(entries: ResolutionLegendEntry[], reference: Pick<ResolutionLegendEntry, "key" | "label">) {
  const key = resolutionLegendKey(reference);
  return entries.find((entry) => resolutionLegendKey(entry) === key)
    || (!reference.key ? entries.find((entry) => entry.label.trim().toLowerCase() === key) : undefined);
}

export function resolutionType(
  entries: ResolutionLegendEntry[],
  title: string,
  key: string | null | undefined,
  legacy: ResolutionLegendEntry[],
) {
  if (key !== undefined) return entries.find((item) => resolutionLegendKey(item) === key);
  if (legacy.length) {
    const matches = legacy.map((entry) => findResolutionLegendEntry(entries, entry));
    const first = matches[0];
    return first && matches.every((entry) => entry && resolutionLegendKey(entry) === resolutionLegendKey(first))
      ? first : undefined;
  }
  const label = title.includes("Advisory") || title.includes("Ad Referendum")
    ? "Advisory/Referendum"
    : title.includes("MMDA") ? "MMDA Resolution"
      : title.includes("Sectoral Committee") ? "Sectoral Committee" : "RDC Resolution";
  return findResolutionLegendEntry(entries, { label });
}
