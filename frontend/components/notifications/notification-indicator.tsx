"use client";

import { useState } from "react";
import { Bell, BellOff, Wifi, WifiOff, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { useNotificationContext } from "./notification-provider";
import { formatDistanceToNow } from "date-fns";
import { useTranslations } from "next-intl";

export function NotificationIndicator() {
  const { isConnected, notifications, clearNotifications } = useNotificationContext();
  const [open, setOpen] = useState(false);
  const t = useTranslations("notifications");

  const unreadCount = notifications.length;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="icon" className="relative">
          {isConnected ? (
            <Bell className="h-5 w-5" />
          ) : (
            <BellOff className="h-5 w-5 text-muted-foreground" />
          )}
          {unreadCount > 0 && (
            <span className="absolute -top-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[10px] text-primary-foreground">
              {unreadCount > 9 ? "9+" : unreadCount}
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-96 p-0" align="end">
        <div className="flex items-center justify-between border-b px-4 py-3">
          <div className="flex items-center gap-2">
            <h4 className="font-semibold">{t("title")}</h4>
            <Badge
              variant={isConnected ? "default" : "secondary"}
              className={cn(
                "h-5 text-xs",
                isConnected ? "bg-green-500 hover:bg-green-500" : ""
              )}
            >
              {isConnected ? (
                <>
                  <Wifi className="mr-1 h-3 w-3" /> {t("live")}
                </>
              ) : (
                <>
                  <WifiOff className="mr-1 h-3 w-3" /> {t("offline")}
                </>
              )}
            </Badge>
          </div>
          {unreadCount > 0 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={clearNotifications}
              className="h-auto py-1 px-2 text-xs"
            >
              {t("clearAll")}
            </Button>
          )}
        </div>

        {notifications.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
            <Bell className="h-8 w-8 mb-2 opacity-50" />
            <p className="text-sm">{t("emptyTitle")}</p>
            <p className="text-xs">{t("emptyDesc")}</p>
          </div>
        ) : (
          <ScrollArea className="h-[300px]">
            <div className="divide-y">
              {notifications.map((notification) => (
                <div
                  key={notification.id}
                  className="px-4 py-3 hover:bg-muted/50 transition-colors"
                >
                  <div className="flex items-start gap-3">
                    <div
                      className={cn(
                        "mt-0.5 h-2 w-2 rounded-full shrink-0",
                        getNotificationColor(notification.type)
                      )}
                    />
                    <div className="flex-1 space-y-1">
                      <p className="text-sm font-medium leading-none">
                        {getNotificationTitle(notification.type, t)}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        {notification.message}
                      </p>
                      <p className="text-xs text-muted-foreground/70">
                        {formatDistanceToNow(new Date(notification.timestamp), {
                          addSuffix: true,
                        })}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </ScrollArea>
        )}
      </PopoverContent>
    </Popover>
  );
}

function getNotificationColor(type: string): string {
  switch (type) {
    case "record_created":
      return "bg-blue-500";
    case "record_approved":
    case "batch_approved":
      return "bg-green-500";
    case "record_rejected":
    case "batch_rejected":
      return "bg-red-500";
    case "export_complete":
    case "sheets_sync_complete":
      return "bg-purple-500";
    case "error":
      return "bg-red-500";
    default:
      return "bg-gray-500";
  }
}

function getNotificationTitle(type: string, t: (key: string) => string): string {
  switch (type) {
    case "record_created":
      return t("newRecord");
    case "record_approved":
      return t("recordApproved");
    case "record_rejected":
      return t("recordRejected");
    case "batch_approved":
      return t("batchApproved");
    case "batch_rejected":
      return t("batchRejected");
    case "batch_extracted":
      return t("batchExtracted");
    case "export_complete":
      return t("exportComplete");
    case "sheets_sync_complete":
      return t("sheetsSynced");
    case "error":
      return t("error");
    default:
      return t("default");
  }
}
