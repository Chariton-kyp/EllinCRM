"use client";

import { useState, useEffect } from "react";
import { AnimatePresence } from "framer-motion";
import { Header } from "./header";
import { Sidebar } from "./sidebar";
import { ChatWidget } from "@/components/chat/chat-widget";
import { cn } from "@/lib/utils";
import { useKeyboardShortcuts } from "@/lib/hooks/use-keyboard-shortcuts";

interface MainLayoutProps {
  children: React.ReactNode;
}

export function MainLayout({ children }: MainLayoutProps) {
  useKeyboardShortcuts();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // Persist collapsed state in localStorage
  useEffect(() => {
    const saved = localStorage.getItem("sidebar-collapsed");
    if (saved !== null) {
      setSidebarCollapsed(saved === "true");
    }
  }, []);

  const handleToggleCollapse = () => {
    const newState = !sidebarCollapsed;
    setSidebarCollapsed(newState);
    localStorage.setItem("sidebar-collapsed", String(newState));
  };

  return (
    <div className="min-h-screen bg-background">
      <Header onMenuClick={() => setSidebarOpen(true)} />
      <div className="flex">
        <Sidebar
          open={sidebarOpen}
          collapsed={sidebarCollapsed}
          onClose={() => setSidebarOpen(false)}
          onToggleCollapse={handleToggleCollapse}
        />
        <main
          className={cn(
            "flex-1 overflow-auto transition-all duration-200",
            // Add margin for sidebar on desktop
            sidebarCollapsed ? "md:ml-16" : "md:ml-64"
          )}
        >
          <div className="container mx-auto p-4 md:p-6 lg:p-8">
            <AnimatePresence mode="wait">
              {children}
            </AnimatePresence>
          </div>
        </main>
      </div>
      <ChatWidget />
    </div>
  );
}
