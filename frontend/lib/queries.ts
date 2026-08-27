"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryResult,
} from "@tanstack/react-query";

import { api, tokenStore } from "@/lib/api";
import type {
  AuthorizeUrlResponse,
  Booking,
  CreatorSession,
  Paginated,
  Session,
  SessionInput,
  User,
} from "@/types/api";

export const keys = {
  me: ["me"] as const,
  sessions: (search: string, page: number) => ["sessions", search, page] as const,
  session: (id: number) => ["session", id] as const,
  bookings: (scope: string) => ["bookings", scope] as const,
  creatorSessions: ["creator-sessions"] as const,
};

/* ------------------------------------------------------------------ auth */

export function useMe(): UseQueryResult<User> {
  return useQuery({
    queryKey: keys.me,
    queryFn: async () => (await api.get<User>("/me/")).data,
    enabled: tokenStore.isAuthenticated,
    retry: false,
    staleTime: 60_000,
  });
}

export function useAuthorizeUrl() {
  return useQuery({
    queryKey: ["authorize-url"],
    queryFn: async () => (await api.get<AuthorizeUrlResponse>("/auth/github/authorize-url/")).data,
    retry: false,
    // A fresh state value per visit to the login page.
    staleTime: 0,
    gcTime: 0,
  });
}

export function useUpdateProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: Partial<Pick<User, "display_name" | "bio" | "avatar_url">>) =>
      (await api.patch<User>("/me/", input)).data,
    onSuccess: (user) => queryClient.setQueryData(keys.me, user),
  });
}

export function useChooseRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (role: "USER" | "CREATOR") =>
      (await api.post<User>("/auth/choose-role/", { role })).data,
    onSuccess: (user) => queryClient.setQueryData(keys.me, user),
  });
}

/* -------------------------------------------------------------- sessions */

export function useSessions(search: string, page: number) {
  return useQuery({
    queryKey: keys.sessions(search, page),
    queryFn: async () =>
      (
        await api.get<Paginated<Session>>("/sessions/", {
          params: { search: search || undefined, page },
        })
      ).data,
    // Availability moves under your feet; a short stale time keeps the catalogue
    // honest without hammering the API.
    staleTime: 15_000,
  });
}

export function useSession(id: number) {
  return useQuery({
    queryKey: keys.session(id),
    queryFn: async () => (await api.get<Session>(`/sessions/${id}/`)).data,
    enabled: Number.isFinite(id),
  });
}

export function useCreatorSessions() {
  return useQuery({
    queryKey: keys.creatorSessions,
    queryFn: async () =>
      (await api.get<Paginated<CreatorSession>>("/creator/sessions/")).data,
  });
}

export function useCreateSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: SessionInput) => (await api.post<Session>("/sessions/", input)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.creatorSessions });
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
    },
  });
}

export function useUpdateSession(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: Partial<SessionInput>) =>
      (await api.patch<Session>(`/sessions/${id}/`, input)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.creatorSessions });
      queryClient.invalidateQueries({ queryKey: keys.session(id) });
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
    },
  });
}

export function useDeleteSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/sessions/${id}/`);
      return id;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.creatorSessions });
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
    },
  });
}

/* -------------------------------------------------------------- bookings */

export function useMyBookings(scope: "active" | "past") {
  return useQuery({
    queryKey: keys.bookings(scope),
    queryFn: async () =>
      (await api.get<Paginated<Booking>>("/bookings/", { params: { scope } })).data,
    enabled: tokenStore.isAuthenticated,
  });
}

export function useBookSession(sessionId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () =>
      (await api.post<Booking>(`/sessions/${sessionId}/book/`)).data,
    // Invalidate on error too: a sold_out response means our cached seat count
    // was stale, and the fresh number is the useful thing to show next.
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: keys.session(sessionId) });
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
      queryClient.invalidateQueries({ queryKey: ["bookings"] });
    },
  });
}

export function useCancelBooking() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (bookingId: number) =>
      (await api.post<Booking>(`/bookings/${bookingId}/cancel/`)).data,
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["bookings"] });
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
      queryClient.invalidateQueries({ queryKey: ["session"] });
    },
  });
}
