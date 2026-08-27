"use client";

import { AlertCircle, CalendarX, Search } from "lucide-react";
import { useEffect, useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { SessionCard } from "@/components/SessionCard";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Field";
import { SessionCardSkeleton } from "@/components/ui/Skeleton";
import { useSessions } from "@/lib/queries";

export default function CatalogPage() {
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  // Debounced so typing doesn't fire a request per keystroke.
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(searchInput.trim());
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchInput]);

  const { data, isLoading, isError, refetch, isFetching } = useSessions(search, page);
  const sessions = data?.results ?? [];
  const totalPages = data ? Math.max(1, Math.ceil(data.count / 12)) : 1;

  return (
    <>
      <PageHeader
        title="Find your next session"
        subtitle="Breathwork, sound, movement and stillness — hosted by people who do this for a living."
      />

      <div className="page mt-8">
        <div className="relative max-w-md">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <Input
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            placeholder="Search sessions"
            aria-label="Search sessions"
            className="pl-9"
          />
        </div>

        <div className="mt-8">
          {isLoading ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 6 }).map((_, index) => (
                <SessionCardSkeleton key={index} />
              ))}
            </div>
          ) : isError ? (
            <EmptyState
              icon={<AlertCircle className="h-5 w-5" />}
              title="Couldn't load sessions"
              description="The API didn't answer. It may still be starting up."
              action={<Button onClick={() => refetch()}>Try again</Button>}
            />
          ) : sessions.length === 0 ? (
            <EmptyState
              icon={<CalendarX className="h-5 w-5" />}
              title={search ? "No sessions match that search" : "No upcoming sessions yet"}
              description={
                search
                  ? "Try a different word, or clear the search to see everything."
                  : "Once a creator publishes a session it will show up here."
              }
              action={
                search ? (
                  <Button variant="secondary" onClick={() => setSearchInput("")}>
                    Clear search
                  </Button>
                ) : undefined
              }
            />
          ) : (
            <>
              <div className="mb-4 text-sm text-muted">
                {data?.count} session{data?.count === 1 ? "" : "s"}
                {search ? ` matching “${search}”` : ""}
              </div>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {sessions.map((session) => (
                  <SessionCard key={session.id} session={session} />
                ))}
              </div>
            </>
          )}
        </div>

        {totalPages > 1 ? (
          <div className="mt-10 flex items-center justify-center gap-3">
            <Button
              variant="secondary"
              size="sm"
              disabled={page === 1 || isFetching}
              onClick={() => setPage((current) => current - 1)}
            >
              Previous
            </Button>
            <span className="text-sm text-muted">
              Page {page} of {totalPages}
            </span>
            <Button
              variant="secondary"
              size="sm"
              disabled={page >= totalPages || isFetching}
              onClick={() => setPage((current) => current + 1)}
            >
              Next
            </Button>
          </div>
        ) : null}
      </div>
    </>
  );
}
