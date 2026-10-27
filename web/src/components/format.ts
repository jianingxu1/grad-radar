import type { SourceName } from "../api";

export const sourceLabels: Record<SourceName, string> = {
  simplify: "Simplify",
  speedyapply: "SpeedyApply",
};

export function formatDate(value: string | null): string {
  if (!value) return "Not provided";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(
    new Date(value),
  );
}
