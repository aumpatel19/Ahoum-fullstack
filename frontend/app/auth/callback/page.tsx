"use client";

import { Loader2 } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { api, asApiError, tokenStore } from "@/lib/api";
import { OAUTH_STATE_KEY } from "@/lib/oauth";
import { keys } from "@/lib/queries";
import type { AuthResponse } from "@/types/api";

function CallbackContent() {
  const router = useRouter();
  const params = useSearchParams();
  const queryClient = useQueryClient();
  // React 18 strict mode mounts effects twice in dev; the OAuth code is
  // single-use, so the second run must not fire a second exchange.
  const exchanged = useRef(false);

  useEffect(() => {
    if (exchanged.current) return;
    exchanged.current = true;

    const error = params.get("error");
    const code = params.get("code");
    const state = params.get("state");
    const expectedState = window.sessionStorage.getItem(OAUTH_STATE_KEY);
    window.sessionStorage.removeItem(OAUTH_STATE_KEY);

    // The user pressed Cancel on GitHub's authorise screen, or GitHub refused.
    if (error) {
      const reason = error === "access_denied" ? "oauth_cancelled" : "oauth_exchange_failed";
      router.replace(`/login?error=${reason}`);
      return;
    }

    if (!code) {
      router.replace("/login?error=oauth_exchange_failed");
      return;
    }

    if (!state || state !== expectedState) {
      router.replace("/login?error=oauth_state_mismatch");
      return;
    }

    api
      .post<AuthResponse>("/auth/oauth/github/", { code })
      .then(({ data }) => {
        tokenStore.set(data.access, data.refresh);
        queryClient.setQueryData(keys.me, data.user);
        // A brand-new account still has to pick a role before it can do anything.
        router.replace(data.is_new_user || !data.user.role_chosen ? "/onboarding/role" : "/");
      })
      .catch((exchangeError) => {
        const apiError = asApiError(exchangeError);
        router.replace(`/login?error=${apiError?.code ?? "oauth_exchange_failed"}`);
      });
  }, [params, queryClient, router]);

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3">
      <Loader2 className="h-6 w-6 animate-spin text-accent" />
      <p className="text-sm text-muted">Finishing sign-in…</p>
    </div>
  );
}

export default function CallbackPage() {
  return (
    <Suspense fallback={null}>
      <CallbackContent />
    </Suspense>
  );
}
