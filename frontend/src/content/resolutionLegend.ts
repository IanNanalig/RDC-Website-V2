export type ResolutionLegendEntry = { key?: string; label: string; color: string };

export function resolutionLegendKey(entry: Pick<ResolutionLegendEntry, "key" | "label">) {
  return entry.key || entry.label.trim().toLowerCase();
}

export function findResolutionLegendEntry(entries: ResolutionLegendEntry[], reference: Pick<ResolutionLegendEntry, "key" | "label">) {
  const key = resolutionLegendKey(reference);
  return entries.find((entry) => resolutionLegendKey(entry) === key)
    || (!reference.key ? entries.find((entry) => entry.label.trim().toLowerCase() === key) : undefined);
}
