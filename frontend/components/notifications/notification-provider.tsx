"use client";

import { createContext, useContext, useEffect, useRef, ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNotifications, Notification } from "@/lib/hooks/use-notifications";
import { useToast } from "@/lib/hooks/use-toast";
import { getStats } from "@/lib/api/records";

interface NotificationContextType {
  isConnected: boolean;
  notifications: Notification[];
  clearNotifications: () => void;
  sendMessage: (message: unknown) => void;
}

const NotificationContext = createContext<NotificationContextType | undefined>(undefined);

interface NotificationProviderProps {
  children: ReactNode;
}

/**
 * Hook that polls stats every 30s and shows a toast when new records appear.
 */
function useNewRecordPolling() {
  const { toast } = useToast();
  const lastKnownCount = useRef<number | null>(null);

  const { data: stats } = useQuery({
    queryKey: ["stats", "polling"],
    queryFn: getStats,
    refetchInterval: 30 * 1000,
    staleTime: 15 * 1000,
  });

  useEffect(() => {
    if (stats == null) return;
    const currentCount = stats.total;

    if (lastKnownCount.current === null) {
      // First load -- just store the count, don't toast
      lastKnownCount.current = currentCount;
      return;
    }

    if (currentCount > lastKnownCount.current) {
      const diff = currentCount - lastKnownCount.current;
      toast({
        title: "New records available",
        description: `${diff} new record${diff > 1 ? "s" : ""} detected.`,
      });
    }

    lastKnownCount.current = currentCount;
  }, [stats, toast]);
}

export function NotificationProvider({ children }: NotificationProviderProps) {
  const notificationData = useNotifications({
    enabled: true,
    autoReconnect: true,
    reconnectInterval: 3000,
    maxReconnectAttempts: 10,
  });

  useNewRecordPolling();

  return (
    <NotificationContext.Provider value={notificationData}>
      {children}
    </NotificationContext.Provider>
  );
}

export function useNotificationContext(): NotificationContextType {
  const context = useContext(NotificationContext);
  if (context === undefined) {
    throw new Error("useNotificationContext must be used within a NotificationProvider");
  }
  return context;
}
