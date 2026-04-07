"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Menu, Sun, Moon } from "lucide-react";
import { useTheme } from "next-themes";
import { NotificationIndicator } from "@/components/notifications/notification-indicator";
import { LanguageSwitcher } from "@/components/layout/language-switcher";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  if (!mounted) {
    return (
      <Button variant="ghost" size="icon" disabled>
        <Skeleton className="h-5 w-5 rounded-full" />
      </Button>
    );
  }

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
      aria-label="Toggle theme"
    >
      {resolvedTheme === "dark" ? (
        <Sun className="h-5 w-5" />
      ) : (
        <Moon className="h-5 w-5" />
      )}
    </Button>
  );
}

interface HeaderProps {
  onMenuClick?: () => void;
}

export function Header({ onMenuClick }: HeaderProps) {
  return (
    <header className="sticky top-0 z-40 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="flex h-16 items-center px-4 md:px-6">
        {/* Mobile menu button */}
        <Button
          variant="ghost"
          size="icon"
          className="mr-2 md:hidden"
          onClick={onMenuClick}
        >
          <Menu className="h-5 w-5" />
          <span className="sr-only">Toggle menu</span>
        </Button>

        {/* Logo */}
        <Link href="/" className="flex items-center space-x-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
            <span className="text-lg font-bold text-primary-foreground">E</span>
          </div>
          <span className="hidden font-bold sm:inline-block">
            EllinCRM
          </span>
        </Link>

        {/* Right side actions */}
        <div className="ml-auto flex items-center space-x-2">
          {/* Notifications */}
          <NotificationIndicator />

          {/* Dark mode toggle */}
          <ThemeToggle />

          {/* Language selector */}
          <LanguageSwitcher />
        </div>
      </div>
    </header>
  );
}
