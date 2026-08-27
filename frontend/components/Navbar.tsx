"use client";

import { CalendarCheck, LayoutDashboard, LogOut, Sparkles, User as UserIcon } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";
import { tokenStore } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useMe } from "@/lib/queries";

export function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const { data: me } = useMe();
  const [authed, setAuthed] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  // localStorage is not reactive; the token store fires an event on every change.
  useEffect(() => {
    const sync = () => setAuthed(tokenStore.isAuthenticated);
    sync();
    window.addEventListener("ahoum:auth", sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener("ahoum:auth", sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  useEffect(() => setMenuOpen(false), [pathname]);

  function signOut() {
    // Logout is client-side only: no refresh-token blacklist in this build
    // (noted in the README's known limitations).
    tokenStore.clear();
    router.push("/login");
  }

  const links = [
    { href: "/", label: "Browse", icon: Sparkles, show: true },
    { href: "/bookings", label: "My bookings", icon: CalendarCheck, show: authed },
    { href: "/creator", label: "Creator", icon: LayoutDashboard, show: Boolean(me?.is_creator) },
  ].filter((link) => link.show);

  return (
    <header className="sticky top-0 z-40 border-b border-border/80 bg-bg/80 backdrop-blur">
      <nav className="page flex h-16 items-center justify-between gap-4">
        <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/15 text-accent">
            <Sparkles className="h-4 w-4" />
          </span>
          Ahoum
        </Link>

        <div className="flex items-center gap-1">
          {links.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className={cn(
                "hidden items-center gap-2 rounded-lg px-3 py-2 text-sm transition sm:inline-flex",
                pathname === href ? "text-content" : "text-muted hover:text-content",
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          ))}

          {authed ? (
            <div className="relative ml-2">
              <button
                onClick={() => setMenuOpen((open) => !open)}
                aria-haspopup="menu"
                aria-expanded={menuOpen}
                className="flex items-center gap-2 rounded-full border border-border p-1 pr-3 transition hover:border-accent/50"
              >
                <Avatar src={me?.avatar_url} name={me?.display_name || me?.username || "You"} size={26} />
                <span className="hidden text-sm text-muted sm:inline">
                  {me?.display_name || me?.username || "Account"}
                </span>
              </button>

              {menuOpen ? (
                <div
                  role="menu"
                  className="absolute right-0 mt-2 w-52 animate-fade-up rounded-xl border border-border bg-surface p-1 shadow-card"
                >
                  <Link
                    href="/profile"
                    className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-muted transition hover:bg-elevated hover:text-content"
                  >
                    <UserIcon className="h-4 w-4" /> Profile
                  </Link>
                  <Link
                    href="/bookings"
                    className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-muted transition hover:bg-elevated hover:text-content sm:hidden"
                  >
                    <CalendarCheck className="h-4 w-4" /> My bookings
                  </Link>
                  <button
                    onClick={signOut}
                    className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-muted transition hover:bg-elevated hover:text-danger"
                  >
                    <LogOut className="h-4 w-4" /> Sign out
                  </button>
                </div>
              ) : null}
            </div>
          ) : (
            <Button size="sm" onClick={() => router.push("/login")} className="ml-2">
              Sign in
            </Button>
          )}
        </div>
      </nav>
    </header>
  );
}
