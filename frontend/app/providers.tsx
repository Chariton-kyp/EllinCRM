"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { useState, useEffect } from "react";
import { Toaster } from "@/components/ui/toaster";
import { NotificationProvider } from "@/components/notifications/notification-provider";
import { useServiceWorker } from "@/lib/hooks/use-service-worker";

function ServiceWorkerRegistration() {
  const { isSupported, isRegistered, isOnline } = useServiceWorker();

  useEffect(() => {
    if (isRegistered) {
      console.log("[PWA] Ready for offline use");
    }
  }, [isRegistered]);

  // Show offline indicator when offline
  if (!isOnline) {
    return (
      <div className="fixed bottom-4 left-4 z-50 rounded-lg bg-yellow-100 px-4 py-2 text-sm text-yellow-800 shadow-lg">
        You are offline. Some features may be limited.
      </div>
    );
  }

  return null;
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30 * 1000, // 30 seconds
            refetchOnWindowFocus: false,
            retry: 1,
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider
        attribute="class"
        defaultTheme="system"
        enableSystem
        disableTransitionOnChange
      >
        <NotificationProvider>
          {children}
          <Toaster />
          <ServiceWorkerRegistration />
        </NotificationProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
