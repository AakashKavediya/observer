import en from "./en.json";

export type TranslationKey = string;

export function t(path: string, fallback?: string): string {
  const parts = path.split(".");
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let current: any = en;
  for (const part of parts) {
    if (current && typeof current === "object" && part in current) {
      current = current[part];
    } else {
      return fallback || path;
    }
  }
  return typeof current === "string" ? current : fallback || path;
}

export default en;
