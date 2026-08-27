"use client";

import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { AuthGuard } from "@/components/AuthGuard";
import { PageHeader } from "@/components/PageHeader";
import { SessionForm } from "@/components/SessionForm";
import { toLocalInputValue } from "@/lib/format";
import { useCreateSession } from "@/lib/queries";

function NewSessionContent() {
  const router = useRouter();
  const create = useCreateSession();

  // Default to tomorrow at the current time: a valid future value out of the box.
  const tomorrow = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString();

  return (
    <>
      <PageHeader title="New session" subtitle="It goes live in the public catalogue immediately." />
      <div className="page mt-8 max-w-2xl">
        <SessionForm
          submitLabel="Publish session"
          pending={create.isPending}
          initial={{
            title: "",
            description: "",
            price: "0.00",
            duration_minutes: 60,
            capacity: 10,
            starts_at: toLocalInputValue(tomorrow),
          }}
          onSubmit={async (input) => {
            const session = await create.mutateAsync(input);
            toast.success("Session published.");
            router.push(`/sessions/${session.id}`);
          }}
        />
      </div>
    </>
  );
}

export default function NewSessionPage() {
  return (
    <AuthGuard requireCreator>
      <NewSessionContent />
    </AuthGuard>
  );
}
