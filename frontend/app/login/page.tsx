"use client";

import { ArrowLeft, Github, ShieldAlert, Sparkles } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { tokenStore } from "@/lib/api";
import { messageForCode } from "@/lib/errors";
import { OAUTH_STATE_KEY } from "@/lib/oauth";
import { useAuthorizeUrl } from "@/lib/queries";

function LoginContent() {
  const router = useRouter();
  const params = useSearchParams();
  const { data, isLoading, refetch } = useAuthorizeUrl();
  const [redirecting, setRedirecting] = useState(false);

  const errorCode = params.get("error");

  // Surface every way the sign-in can fail, including the user pressing
  // "Cancel" on GitHub's authorise screen.
  useEffect(() => {
    if (!errorCode) return;
    toast.error(messageForCode(errorCode, "Sign-in didn't complete."));
    router.replace("/login");
  }, [errorCode, router]);

  useEffect(() => {
    if (tokenStore.isAuthenticated) router.replace("/");
  }, [router]);

  async function signIn() {
    setRedirecting(true);
    const fresh = data?.configured ? data : (await refetch()).data;
    if (!fresh?.configured || !fresh.authorize_url || !fresh.state) {
      setRedirecting(false);
      toast.error(messageForCode(fresh?.code ?? "oauth_not_configured"));
      return;
    }
    // The state is kept here and compared on the way back, so a callback that
    // did not originate from this tab is rejected.
    window.sessionStorage.setItem(OAUTH_STATE_KEY, fresh.state);
    window.location.href = fresh.authorize_url;
  }

  const notConfigured = data && !data.configured;

  return (
    <div className="page flex min-h-[calc(100vh-4rem)] flex-col items-center justify-center py-16">
      <div className="w-full max-w-md">
        {/* An explicit way out. Signing in is optional - browsing is not gated -
            so this page must never be a dead end, at any screen width. */}
        <Link
          href="/"
          className="mb-4 inline-flex items-center gap-2 text-sm text-muted transition hover:text-content"
        >
          <ArrowLeft className="h-4 w-4" /> Back to sessions
        </Link>
      </div>

      <Card className="aurora w-full max-w-md p-8">
        <span className="inline-flex h-11 w-11 items-center justify-center rounded-xl bg-accent/15 text-accent">
          <Sparkles className="h-5 w-5" />
        </span>

        <h1 className="mt-6 text-2xl font-semibold tracking-tight">Welcome to Ahoum</h1>
        <p className="mt-2 text-sm text-muted">
          Sign in with GitHub to book sessions, or to publish your own as a creator.
        </p>

        <Button
          className="mt-8 w-full"
          onClick={signIn}
          loading={redirecting || isLoading}
          icon={<Github className="h-4 w-4" />}
          disabled={notConfigured}
        >
          Continue with GitHub
        </Button>

        {notConfigured ? (
          <div className="mt-4 flex gap-2 rounded-xl border border-warn/30 bg-warn/10 p-3 text-xs text-warn">
            <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
            <span>
              GitHub OAuth isn&apos;t configured on the server. Add{" "}
              <code className="font-mono">GITHUB_CLIENT_ID</code> and{" "}
              <code className="font-mono">GITHUB_CLIENT_SECRET</code> to <code className="font-mono">.env</code>,
              then restart the backend. See the README.
            </span>
          </div>
        ) : null}

        <p className="mt-6 text-xs leading-relaxed text-muted">
          GitHub only tells us who you are. The access and refresh tokens this app
          uses are issued by its own backend.
        </p>
      </Card>

      <p className="mt-6 text-center text-xs text-muted">
        You don&apos;t need an account to browse.{" "}
        <Link href="/" className="text-accent transition hover:text-accent-hover">
          Keep looking around
        </Link>
        .
      </p>
    </div>
  );
}

export default function LoginPage() {
  // useSearchParams needs a suspense boundary to keep the route statically renderable.
  return (
    <Suspense fallback={null}>
      <LoginContent />
    </Suspense>
  );
}
