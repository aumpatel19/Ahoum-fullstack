"use client";

import { CalendarHeart, Loader2, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { tokenStore } from "@/lib/api";
import { cn } from "@/lib/cn";
import { errorMessage } from "@/lib/errors";
import { useChooseRole, useMe } from "@/lib/queries";
import type { Role } from "@/types/api";

const OPTIONS: { value: Role; title: string; description: string; icon: typeof Sparkles }[] = [
  {
    value: "USER",
    title: "I'm here to attend",
    description: "Browse the catalogue, book a seat, manage your bookings.",
    icon: CalendarHeart,
  },
  {
    value: "CREATOR",
    title: "I'm here to host",
    description: "Publish sessions, set capacity, and watch who books them.",
    icon: Sparkles,
  },
];

export default function RoleOnboardingPage() {
  const router = useRouter();
  const { data: me, isLoading } = useMe();
  const chooseRole = useChooseRole();
  const [selected, setSelected] = useState<Role>("USER");

  useEffect(() => {
    if (!tokenStore.isAuthenticated) router.replace("/login?error=not_authenticated");
  }, [router]);

  // The choice is one-time and server-enforced; anyone who already made it is
  // sent on rather than shown a form that would only 409.
  useEffect(() => {
    if (me?.role_chosen) router.replace(me.is_creator ? "/creator" : "/");
  }, [me, router]);

  function confirm() {
    chooseRole.mutate(selected, {
      onSuccess: (user) => {
        toast.success(user.is_creator ? "You're set up as a creator." : "You're all set.");
        router.replace(user.is_creator ? "/creator" : "/");
      },
      onError: (error) => toast.error(errorMessage(error, "Couldn't save your choice.")),
    });
  }

  if (isLoading || !me || me.role_chosen) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted" />
      </div>
    );
  }

  return (
    <div className="page flex min-h-[calc(100vh-4rem)] items-center justify-center py-16">
      <Card className="w-full max-w-lg p-8">
        <h1 className="text-2xl font-semibold tracking-tight">
          Nice to meet you, {me.display_name || me.username}
        </h1>
        <p className="mt-2 text-sm text-muted">
          How will you use Ahoum? This is set once and can&apos;t be changed later.
        </p>

        <div className="mt-6 space-y-3">
          {OPTIONS.map(({ value, title, description, icon: Icon }) => (
            <button
              key={value}
              onClick={() => setSelected(value)}
              aria-pressed={selected === value}
              className={cn(
                "flex w-full items-start gap-4 rounded-xl border p-4 text-left transition",
                selected === value
                  ? "border-accent bg-accent/10"
                  : "border-border bg-elevated hover:border-accent/40",
              )}
            >
              <span
                className={cn(
                  "mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg",
                  selected === value ? "bg-accent/20 text-accent" : "bg-surface text-muted",
                )}
              >
                <Icon className="h-4 w-4" />
              </span>
              <span>
                <span className="block font-medium text-content">{title}</span>
                <span className="mt-0.5 block text-sm text-muted">{description}</span>
              </span>
            </button>
          ))}
        </div>

        <Button className="mt-6 w-full" onClick={confirm} loading={chooseRole.isPending}>
          Continue
        </Button>

        {/* The choice is required before anything else works, so the only honest
            escape from this screen is signing back out. */}
        <button
          onClick={() => {
            tokenStore.clear();
            router.replace("/");
          }}
          className="mx-auto mt-4 block text-xs text-muted transition hover:text-content"
        >
          Not now — sign out and keep browsing
        </button>
      </Card>
    </div>
  );
}
