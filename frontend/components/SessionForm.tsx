"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { FieldError, Input, Label, Textarea } from "@/components/ui/Field";
import { errorMessage, fieldErrors } from "@/lib/errors";
import { fromLocalInputValue } from "@/lib/format";
import type { SessionInput } from "@/types/api";

/**
 * Client-side validation is here to give fast, friendly feedback. The same rules
 * are enforced again in the serializer, which is the copy that actually matters.
 */
const schema = z.object({
  title: z.string().trim().min(3, "Give it a title of at least 3 characters.").max(200),
  description: z.string().trim().max(5000).optional().default(""),
  price: z
    .string()
    .refine((value) => !Number.isNaN(Number(value)) && Number(value) >= 0, "Price can't be negative."),
  duration_minutes: z
    .number()
    .int()
    .min(5, "Sessions run for at least 5 minutes.")
    .max(1440, "Keep it under 24 hours."),
  capacity: z.number().int().min(1, "Capacity must be at least 1.").max(32767),
  starts_at: z.string().min(1, "Pick a start time."),
});

export interface SessionFormValues {
  title: string;
  description: string;
  price: string;
  duration_minutes: number;
  capacity: number;
  /** Local `datetime-local` value, e.g. 2026-01-02T18:30 */
  starts_at: string;
}

export function SessionForm({
  initial,
  submitLabel,
  requireFutureStart = true,
  onSubmit,
  pending,
}: {
  initial: SessionFormValues;
  submitLabel: string;
  requireFutureStart?: boolean;
  onSubmit: (input: SessionInput) => Promise<unknown>;
  pending: boolean;
}) {
  const router = useRouter();
  const [values, setValues] = useState<SessionFormValues>(initial);
  const [errors, setErrors] = useState<Record<string, string>>({});

  function update<K extends keyof SessionFormValues>(key: K, value: SessionFormValues[K]) {
    setValues((current) => ({ ...current, [key]: value }));
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setErrors({});

    const parsed = schema.safeParse(values);
    if (!parsed.success) {
      setErrors(
        Object.fromEntries(
          parsed.error.issues.map((issue) => [String(issue.path[0]), issue.message]),
        ),
      );
      return;
    }

    if (requireFutureStart && new Date(values.starts_at).getTime() <= Date.now()) {
      setErrors({ starts_at: "Start time must be in the future." });
      return;
    }

    try {
      await onSubmit({
        title: parsed.data.title,
        description: parsed.data.description ?? "",
        price: Number(parsed.data.price).toFixed(2),
        duration_minutes: parsed.data.duration_minutes,
        capacity: parsed.data.capacity,
        starts_at: fromLocalInputValue(values.starts_at),
      });
    } catch (error) {
      setErrors(fieldErrors(error));
      toast.error(errorMessage(error, "Couldn't save the session."));
    }
  }

  return (
    <Card className="p-6">
      <form onSubmit={submit} className="space-y-5" noValidate>
        <div>
          <Label htmlFor="title">Title</Label>
          <Input
            id="title"
            value={values.title}
            onChange={(event) => update("title", event.target.value)}
            placeholder="Sunrise Breathwork"
          />
          <FieldError message={errors.title} />
        </div>

        <div>
          <Label htmlFor="description">Description</Label>
          <Textarea
            id="description"
            value={values.description}
            onChange={(event) => update("description", event.target.value)}
            placeholder="What happens in the session, what to bring, who it's for."
          />
          <FieldError message={errors.description} />
        </div>

        <div className="grid gap-5 sm:grid-cols-2">
          <div>
            <Label htmlFor="starts_at">Starts at</Label>
            <Input
              id="starts_at"
              type="datetime-local"
              value={values.starts_at}
              onChange={(event) => update("starts_at", event.target.value)}
            />
            <FieldError message={errors.starts_at} />
          </div>

          <div>
            <Label htmlFor="duration_minutes">Duration (minutes)</Label>
            <Input
              id="duration_minutes"
              type="number"
              min={5}
              max={1440}
              value={values.duration_minutes}
              onChange={(event) => update("duration_minutes", Number(event.target.value))}
            />
            <FieldError message={errors.duration_minutes} />
          </div>

          <div>
            <Label htmlFor="capacity">Capacity</Label>
            <Input
              id="capacity"
              type="number"
              min={1}
              value={values.capacity}
              onChange={(event) => update("capacity", Number(event.target.value))}
            />
            <FieldError message={errors.capacity} />
            <p className="mt-1.5 text-xs text-muted">
              Can&apos;t be lowered below the number of seats already booked.
            </p>
          </div>

          <div>
            <Label htmlFor="price">Price</Label>
            <Input
              id="price"
              type="number"
              min={0}
              step="0.01"
              value={values.price}
              onChange={(event) => update("price", event.target.value)}
            />
            <FieldError message={errors.price} />
          </div>
        </div>

        <div className="flex justify-end gap-2 border-t border-border/70 pt-5">
          <Button type="button" variant="secondary" onClick={() => router.back()}>
            Cancel
          </Button>
          <Button type="submit" loading={pending}>
            {submitLabel}
          </Button>
        </div>
      </form>
    </Card>
  );
}
