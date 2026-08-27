"use client";

import {
  CalendarCheck,
  LayoutDashboard,
  LogOut,
  Menu,
  Sparkles,
  User as UserIcon,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ComponentType } from "react";

import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";
import { tokenStore } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useMe } from "@/lib/queries";

interface NavLink {
  href: string;
  label: string;
  icon: ComponentType<{ className?: string }>;
}

export function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const { data: me } = useMe();
  const [authed, setAuthed] = useState(false);
  const [menu, setMenu] = useState<"none" | "account" | "mobile">("none");

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

  // Any navigation closes whatever is open.
  useEffect(() => setMenu("none"), [pathname]);

  useEffect(() => {
    if (menu === "none") return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMenu("none");
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [menu]);

  function signOut() {
    // Logout is client-side only: no refresh-token blacklist in this build
    // (noted in the README's known limitations).
    tokenStore.clear();
    setMenu("none");
    router.push("/login");
  }

  const links: NavLink[] = [
    { href: "/", label: "Browse", icon: Sparkles },
    ...(authed ? [{ href: "/bookings", label: "My bookings", icon: CalendarCheck }] : []),
    ...(me?.is_creator ? [{ href: "/creator", label: "Creator", icon: LayoutDashboard }] : []),
  ];

  const onLoginPage = pathname === "/login";
  const displayName = me?.display_name || me?.username || "Account";

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
          {/* Wide screens: the links sit in the bar. */}
          {links.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              aria-current={pathname === href ? "page" : undefined}
              className={cn(
                "hidden items-center gap-2 rounded-lg px-3 py-2 text-sm transition sm:inline-flex",
                // An active link that only changes text colour reads as broken:
                // you click it, nothing happens, and nothing says why.
                pathname === href
                  ? "bg-elevated text-content"
                  : "text-muted hover:bg-elevated/60 hover:text-content",
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          ))}

          {authed ? (
            <div className="relative ml-1">
              <button
                onClick={() => setMenu((current) => (current === "account" ? "none" : "account"))}
                aria-haspopup="menu"
                aria-expanded={menu === "account"}
                aria-label={`Account menu for ${displayName}`}
                className="flex items-center gap-2 rounded-full border border-border p-1 transition hover:border-accent/50 sm:pr-3"
              >
                <Avatar src={me?.avatar_url} name={displayName} size={26} />
                <span className="hidden text-sm text-muted sm:inline">{displayName}</span>
              </button>

              {menu === "account" ? (
                <>
                  <div
                    className="fixed inset-0 z-10 cursor-default"
                    aria-hidden
                    onClick={() => setMenu("none")}
                  />
                  <div
                    role="menu"
                    className="absolute right-0 z-20 mt-2 w-56 animate-fade-up rounded-xl border border-border bg-surface p-1 shadow-card"
                  >
                    <p className="truncate px-3 py-2 text-xs text-muted">
                      Signed in as <span className="text-content">{displayName}</span>
                    </p>
                    <div className="my-1 h-px bg-border" />

                    {/* Repeated here so every destination is reachable from one
                        place, at any screen width. */}
                    {links.map(({ href, label, icon: Icon }) => (
                      <MenuLink key={href} href={href} icon={Icon} className="sm:hidden">
                        {label}
                      </MenuLink>
                    ))}

                    <MenuLink href="/profile" icon={UserIcon}>
                      Profile
                    </MenuLink>

                    <button
                      onClick={signOut}
                      role="menuitem"
                      className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-muted transition hover:bg-elevated hover:text-danger"
                    >
                      <LogOut className="h-4 w-4" /> Sign out
                    </button>
                  </div>
                </>
              ) : null}
            </div>
          ) : (
            // No point offering "Sign in" to someone already on the sign-in page.
            !onLoginPage && (
              <Button size="sm" onClick={() => router.push("/login")} className="ml-1">
                Sign in
              </Button>
            )
          )}

          {/* Narrow screens: signed-out visitors still need the links, and there
              is no avatar menu to hide them in. */}
          {!authed ? (
            <div className="relative sm:hidden">
              <button
                onClick={() => setMenu((current) => (current === "mobile" ? "none" : "mobile"))}
                aria-haspopup="menu"
                aria-expanded={menu === "mobile"}
                aria-label="Menu"
                className="ml-1 flex h-9 w-9 items-center justify-center rounded-lg border border-border text-muted transition hover:border-accent/50 hover:text-content"
              >
                {menu === "mobile" ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
              </button>

              {menu === "mobile" ? (
                <>
                  <div
                    className="fixed inset-0 z-10 cursor-default"
                    aria-hidden
                    onClick={() => setMenu("none")}
                  />
                  <div
                    role="menu"
                    className="absolute right-0 z-20 mt-2 w-52 animate-fade-up rounded-xl border border-border bg-surface p-1 shadow-card"
                  >
                    {links.map(({ href, label, icon: Icon }) => (
                      <MenuLink key={href} href={href} icon={Icon}>
                        {label}
                      </MenuLink>
                    ))}
                    {!onLoginPage ? (
                      <MenuLink href="/login" icon={UserIcon}>
                        Sign in
                      </MenuLink>
                    ) : null}
                  </div>
                </>
              ) : null}
            </div>
          ) : null}
        </div>
      </nav>
    </header>
  );
}

function MenuLink({
  href,
  icon: Icon,
  className,
  children,
}: {
  href: string;
  icon: ComponentType<{ className?: string }>;
  className?: string;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const active = pathname === href;
  return (
    <Link
      href={href}
      role="menuitem"
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition hover:bg-elevated hover:text-content",
        active ? "bg-elevated text-content" : "text-muted",
        className,
      )}
    >
      <Icon className="h-4 w-4" />
      {children}
      {active ? <span className="ml-auto text-[10px] uppercase text-muted">here</span> : null}
    </Link>
  );
}
