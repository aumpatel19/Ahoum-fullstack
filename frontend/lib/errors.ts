import { asApiError } from "@/lib/api";

/**
 * The API sends a stable machine code with every error. The UI owns the wording,
 * which means copy changes never require a backend deploy and the frontend never
 * matches on English prose.
 */
const MESSAGES: Record<string, string> = {
  sold_out: "That was the last seat — this session just sold out.",
  duplicate: "You already have an active booking for this session.",
  already_started: "This session has already started.",
  already_cancelled: "That booking was already cancelled.",
  not_found: "We couldn't find that — it may have been removed.",
  not_authenticated: "Please sign in to continue.",
  token_not_valid: "Your session expired. Please sign in again.",
  permission_denied: "Your account doesn't have access to that.",
  role_already_chosen: "Your role has already been set and can't be changed.",
  oauth_cancelled: "GitHub sign-in was cancelled.",
  oauth_exchange_failed: "GitHub couldn't complete the sign-in. Please try again.",
  oauth_not_configured:
    "GitHub OAuth isn't configured on the server. Add GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET to .env.",
  oauth_state_mismatch: "The sign-in request didn't match. Please start again.",
  github_unreachable: "Couldn't reach GitHub. Check your connection and try again.",
  session_expired: "Your session expired. Please sign in again.",
  validation_error: "Please check the highlighted fields.",
};

export function messageForCode(code: string | null | undefined, fallback = "Something went wrong."): string {
  if (!code) return fallback;
  return MESSAGES[code] ?? fallback;
}

/** Turn any thrown value into something worth showing a person. */
export function errorMessage(error: unknown, fallback = "Something went wrong."): string {
  const apiError = asApiError(error);
  if (!apiError) return fallback;
  return MESSAGES[apiError.code] ?? apiError.detail ?? fallback;
}

/** Field-level errors from a DRF ValidationError, for inline form messages. */
export function fieldErrors(error: unknown): Record<string, string> {
  const apiError = asApiError(error);
  if (!apiError?.errors) return {};
  return Object.fromEntries(
    Object.entries(apiError.errors).map(([field, messages]) => [
      field,
      Array.isArray(messages) ? messages.join(" ") : String(messages),
    ]),
  );
}
