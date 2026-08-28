import { Badge } from "@/components/ui/Badge";
import type { Session } from "@/types/api";

/**
 * Availability shown here is a *hint*, not a promise: it is a number that was
 * true when the page rendered. The authoritative answer only exists at the
 * moment the booking is written, which is why the API can still answer
 * "sold out" to a button this pill says is bookable. See DECISIONS.md D1.
 */
export function SeatsPill({ session }: { session: Session }) {
  if (session.has_started) return <Badge tone="neutral">Past</Badge>;
  if (session.is_sold_out) return <Badge tone="danger">Sold out</Badge>;
  if (session.seats_remaining <= 3) {
    return (
      <Badge tone="warn">
        {session.seats_remaining} seat{session.seats_remaining === 1 ? "" : "s"} left
      </Badge>
    );
  }
  // Neutral when there is plenty of room: colour is reserved for the states
  // that should make someone hurry, so amber and red actually stand out.
  return <Badge tone="neutral">{session.seats_remaining} seats left</Badge>;
}
