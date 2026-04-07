"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import {
  LayoutDashboard,
  FileSearch,
  FileText,
  X,
  ChevronLeft,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface SidebarProps {
  open?: boolean;
  collapsed?: boolean;
  onClose?: () => void;
  onToggleCollapse?: () => void;
}

const navigationItems = [
  {
    key: "dashboard",
    href: "/",
    icon: LayoutDashboard,
  },
  {
    key: "extraction",
    href: "/extraction",
    icon: FileSearch,
  },
  {
    key: "records",
    href: "/records",
    icon: FileText,
  },
];

export function Sidebar({
  open = false,
  collapsed = false,
  onClose,
  onToggleCollapse
}: SidebarProps) {
  const pathname = usePathname();
  const t = useTranslations("nav");
  const tCommon = useTranslations("common");

  return (
    <>
      {/* Mobile overlay */}
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed left-0 top-16 z-30 h-[calc(100vh-4rem)] transform border-r bg-background transition-all duration-200 ease-in-out",
          // Mobile: slide in/out
          open ? "translate-x-0" : "-translate-x-full",
          // Desktop: always visible but can be collapsed
          "md:translate-x-0",
          collapsed ? "md:w-16" : "md:w-64"
        )}
      >
        {/* Mobile close button */}
        <div className="flex h-12 items-center justify-between border-b px-4 md:hidden">
          <span className="font-bold">{tCommon("appName")}</span>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-5 w-5" />
          </Button>
        </div>

        {/* Desktop collapse toggle */}
        <div className="hidden h-12 items-center justify-end border-b px-2 md:flex">
          <Button
            variant="ghost"
            size="icon"
            onClick={onToggleCollapse}
            className="h-8 w-8"
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            <ChevronLeft className={cn(
              "h-4 w-4 transition-transform",
              collapsed && "rotate-180"
            )} />
          </Button>
        </div>

        {/* Navigation */}
        <nav className="flex flex-col gap-2 p-2 md:p-2">
          {navigationItems.map((item) => {
            const isActive = pathname === item.href;
            const name = t(item.key);
            return (
              <Link
                key={item.key}
                href={item.href}
                onClick={onClose}
                title={collapsed ? name : undefined}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 transition-colors",
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground",
                  collapsed && "md:justify-center md:px-2"
                )}
              >
                <item.icon className="h-5 w-5 shrink-0" />
                {!collapsed && (
                  <div className="flex flex-col md:block">
                    <span className="text-sm font-medium">{name}</span>
                  </div>
                )}
              </Link>
            );
          })}
        </nav>

        {/* Footer */}
        <div className={cn(
          "absolute bottom-0 left-0 right-0 border-t p-3",
          collapsed && "md:p-2"
        )}>
          <div className={cn(
            "text-xs text-muted-foreground",
            collapsed && "md:text-center"
          )}>
            {collapsed ? (
              <p className="hidden md:block" title="EllinCRM v1.0">EC</p>
            ) : (
              <>
                <p>EllinCRM</p>
                <p>AI Document Automation v1.0</p>
              </>
            )}
            <p className="md:hidden">EllinCRM</p>
            <p className="md:hidden">AI Document Automation v1.0</p>
          </div>
        </div>
      </aside>
    </>
  );
}
