"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { tokenStore } from "@/lib/api";
import { useMe } from "@/lib/queries";

/**
 * Convenience, not security.
 *
 * This only decides what to render. Every endpoint behind it re-checks the
 * token and the role server-side, so bypassing this component in devtools buys
 * an attacker a nicer-looking 401 page and nothing else.
 */
export function AuthGuard({
  children,
  requireCreator = false,
}: {
  children: ReactNode;
  requireCreator?: boolean;
}) {
  const router = useRouter();
  const { data: me, isLoading, isError } = useMe();

  useEffect(() => {
    if (!tokenStore.isAuthenticated) {
      router.replace("/login?error=not_authenticated");
      return;
    }
    if (isError) router.replace("/login?error=session_expired");
  }, [isError, router]);

  useEffect(() => {
    if (me && !me.role_chosen) router.replace("/onboarding/role");
  }, [me, router]);

  if (isLoading || !me) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted" />
      </div>
    );
  }

  if (requireCreator && !me.is_creator) {
    return (
      <div className="page py-20 text-center">
        <h1 className="text-xl font-semibold">Creators only</h1>
        <p className="mt-2 text-sm text-muted">
          This area is for creator accounts. Your account is set up as a regular user.
        </p>
      </div>
    );
  }

  return <>{children}</>;
}
