"use client";

import { useParams, useRouter } from "next/navigation";
import { toast } from "sonner";

import { AuthGuard } from "@/components/AuthGuard";
import { PageHeader } from "@/components/PageHeader";
import { SessionForm } from "@/components/SessionForm";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { toLocalInputValue } from "@/lib/format";
import { useSession, useUpdateSession } from "@/lib/queries";

function EditSessionContent() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const sessionId = Number(params.id);
  const { data: session, isLoading, isError } = useSession(sessionId);
  const update = useUpdateSession(sessionId);

  if (isLoading) {
    return (
      <div className="page mt-8 max-w-2xl">
        <Skeleton className="h-96 w-full rounded-2xl" />
      </div>
    );
  }

  if (isError || !session) {
    return (
      <div className="page py-20 text-center">
        <h1 className="text-xl font-semibold">Session not found</h1>
        <p className="mt-2 text-sm text-muted">
          You can only edit sessions you created — the API returns 404 for anyone else&apos;s.
        </p>
        <Button className="mt-6" variant="secondary" onClick={() => router.push("/creator")}>
          Back to dashboard
        </Button>
      </div>
    );
  }

  return (
    <>
      <PageHeader
        title="Edit session"
        subtitle={`${session.seats_taken} of ${session.capacity} seats are already booked.`}
      />
      <div className="page mt-8 max-w-2xl">
        <SessionForm
          submitLabel="Save changes"
          pending={update.isPending}
          // An existing session may already have started; editing its copy is fine.
          requireFutureStart={false}
          initial={{
            title: session.title,
            description: session.description,
            price: session.price,
            duration_minutes: session.duration_minutes,
            capacity: session.capacity,
            starts_at: toLocalInputValue(session.starts_at),
          }}
          onSubmit={async (input) => {
            await update.mutateAsync(input);
            toast.success("Session updated.");
            router.push("/creator");
          }}
        />
      </div>
    </>
  );
}

export default function EditSessionPage() {
  return (
    <AuthGuard requireCreator>
      <EditSessionContent />
    </AuthGuard>
  );
}
