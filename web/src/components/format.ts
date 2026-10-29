export function sourceLabel(name: string): string {
  if (name === "simplify") return "Simplify";
  if (name === "speedyapply") return "SpeedyApply";
  const [platform, board] = name.split(":", 2);
  if (!board) return name;
  const knownCompanyNames: Record<string, string> = { openai: "OpenAI", shieldai: "Shield AI" };
  const company =
    knownCompanyNames[board] ??
    board.replace(/[-_]/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
  return `${company} (${platform[0]?.toUpperCase()}${platform.slice(1)})`;
}

export function formatDate(value: string | null): string {
  if (!value) return "Not provided";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(
    new Date(value),
  );
}
