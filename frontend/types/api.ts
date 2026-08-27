/** Mirrors the DRF serializers. Nothing in the app uses `any`. */

export type Role = "USER" | "CREATOR";
export type BookingStatus = "CONFIRMED" | "CANCELLED";

export interface User {
  id: number;
  username: string;
  email: string;
  role: Role;
  role_chosen: boolean;
  is_creator: boolean;
  display_name: string;
  bio: string;
  avatar_url: string;
  date_joined: string;
}

export interface PublicUser {
  id: number;
  display_name: string;
  avatar_url: string;
}

export interface Session {
  id: number;
  title: string;
  description: string;
  /** DRF serialises Decimal as a string so precision survives the round trip. */
  price: string;
  duration_minutes: number;
  starts_at: string;
  capacity: number;
  seats_taken: number;
  seats_remaining: number;
  is_sold_out: boolean;
  has_started: boolean;
  creator: PublicUser;
  created_at: string;
}

export interface CreatorSession extends Session {
  confirmed_bookings: number;
  is_active: boolean;
}

export interface Booking {
  id: number;
  status: BookingStatus;
  created_at: string;
  cancelled_at: string | null;
  session: Session;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface AuthResponse {
  access: string;
  refresh: string;
  is_new_user: boolean;
  user: User;
}

export interface AuthorizeUrlResponse {
  configured: boolean;
  authorize_url?: string;
  state?: string;
  detail?: string;
  code?: string;
}

export interface ApiError {
  detail: string;
  code: string;
  errors?: Record<string, string[]>;
}

export interface SessionInput {
  title: string;
  description: string;
  price: string;
  duration_minutes: number;
  starts_at: string;
  capacity: number;
}
