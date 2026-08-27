import clsx, { type ClassValue } from "clsx";

/** Tiny class-name joiner. No tailwind-merge: variants below never conflict. */
export function cn(...values: ClassValue[]): string {
  return clsx(values);
}
