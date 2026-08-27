"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/AuthGuard";
import { PageHeader } from "@/components/PageHeader";
import { Avatar } from "@/components/ui/Avatar";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { FieldError, Input, Label, Textarea } from "@/components/ui/Field";
import { errorMessage, fieldErrors } from "@/lib/errors";
import { useMe, useUpdateProfile } from "@/lib/queries";

function ProfileContent() {
  const { data: me } = useMe();
  const update = useUpdateProfile();
  const [form, setForm] = useState({ display_name: "", bio: "", avatar_url: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!me) return;
    setForm({ display_name: me.display_name, bio: me.bio, avatar_url: me.avatar_url });
  }, [me]);

  function save() {
    setErrors({});
    update.mutate(form, {
      onSuccess: () => toast.success("Profile updated."),
      onError: (error) => {
        setErrors(fieldErrors(error));
        toast.error(errorMessage(error, "Couldn't save your profile."));
      },
    });
  }

  if (!me) return null;

  return (
    <>
      <PageHeader title="Your profile" subtitle="The details other people see next to your name." />

      <div className="page mt-8 max-w-2xl">
        <Card className="p-6">
          <div className="flex items-center gap-4">
            <Avatar src={form.avatar_url} name={form.display_name || me.username} size={56} />
            <div>
              <p className="font-medium">{form.display_name || me.username}</p>
              <p className="mt-0.5 flex items-center gap-2 text-xs text-muted">
                @{me.username}
                <Badge tone={me.is_creator ? "accent" : "neutral"}>
                  {me.is_creator ? "Creator" : "User"}
                </Badge>
              </p>
            </div>
          </div>

          <div className="mt-8 space-y-5">
            <div>
              <Label htmlFor="display_name">Display name</Label>
              <Input
                id="display_name"
                value={form.display_name}
                maxLength={100}
                onChange={(event) => setForm({ ...form, display_name: event.target.value })}
              />
              <FieldError message={errors.display_name} />
            </div>

            <div>
              <Label htmlFor="bio">Bio</Label>
              <Textarea
                id="bio"
                value={form.bio}
                maxLength={1000}
                placeholder="A line or two about you."
                onChange={(event) => setForm({ ...form, bio: event.target.value })}
              />
              <FieldError message={errors.bio} />
            </div>

            <div>
              <Label htmlFor="avatar_url">Avatar URL</Label>
              <Input
                id="avatar_url"
                value={form.avatar_url}
                placeholder="https://…"
                onChange={(event) => setForm({ ...form, avatar_url: event.target.value })}
              />
              <FieldError message={errors.avatar_url} />
            </div>
          </div>

          <div className="mt-8 flex items-center justify-between gap-4 border-t border-border/70 pt-5">
            <p className="text-xs text-muted">
              Your role is fixed at sign-up and can&apos;t be edited here — the API ignores it even
              if the request contains it.
            </p>
            <Button onClick={save} loading={update.isPending}>
              Save changes
            </Button>
          </div>
        </Card>
      </div>
    </>
  );
}

export default function ProfilePage() {
  return (
    <AuthGuard>
      <ProfileContent />
    </AuthGuard>
  );
}
