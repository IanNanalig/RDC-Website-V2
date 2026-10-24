export type SortDirection = "asc" | "desc";
export type SortOption = { key: string; label: string };

export function sortRows<T>(
  rows: T[],
  sortKey: string | null,
  direction: SortDirection,
  getValue: (row: T, key: string) => string | number | null | undefined,
): T[] {
  if (!sortKey) return rows;
  const multiplier = direction === "asc" ? 1 : -1;
  return rows
    .map((row, index) => ({ row, index, value: getValue(row, sortKey) }))
    .sort((left, right) => {
      const leftEmpty = left.value === null || left.value === undefined || left.value === "";
      const rightEmpty = right.value === null || right.value === undefined || right.value === "";
      if (leftEmpty || rightEmpty) {
        if (leftEmpty !== rightEmpty) return leftEmpty ? 1 : -1;
        return left.index - right.index;
      }
      let result = 0;
      if (typeof left.value === "number" && typeof right.value === "number") {
        result = left.value - right.value;
      } else {
        result = String(left.value).localeCompare(String(right.value), undefined, {
          sensitivity: "base",
          numeric: true,
        });
      }
      return result ? result * multiplier : left.index - right.index;
    })
    .map(({ row }) => row);
}
