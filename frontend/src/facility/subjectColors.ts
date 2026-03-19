export const SUBJECT_COLORS = [
  "#5B8FB9",
  "#4A9B8E",
  "#B89B5B",
  "#9B6B7A",
  "#7A9B6B",
  "#7A6B9B",
] as const;

// Stable assignment: sort players by ID, then assign by index
function getSubjectColor(playerIndex: number): string {
  return SUBJECT_COLORS[playerIndex % SUBJECT_COLORS.length];
}

// Build a stable ID→color map that survives reconnections
export function buildColorMap(playerIds: string[]): Record<string, string> {
  const sorted = [...playerIds].sort();
  return Object.fromEntries(sorted.map((id, i) => [id, getSubjectColor(i)]));
}
