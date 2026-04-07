"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useToast } from "./use-toast";
import { useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";

export interface Notification {
    type: string;
    id: string;
    timestamp: string;
    data: Record<string, unknown>;
    message: string;
}

interface UseNotificationsOptions {
    enabled?: boolean;
    autoReconnect?: boolean;
    reconnectInterval?: number;
    maxReconnectAttempts?: number;
}

interface UseNotificationsReturn {
    isConnected: boolean;
    notifications: Notification[];
    clearNotifications: () => void;
    sendMessage: (message: unknown) => void;
}

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:7000/ws/notifications";

export function useNotifications(
    options: UseNotificationsOptions = {}
): UseNotificationsReturn {
    const {
        enabled = true,
        autoReconnect = true,
        reconnectInterval = 3000,
        maxReconnectAttempts = 5,
    } = options;

    const { toast } = useToast();
    const queryClient = useQueryClient();
    const t = useTranslations("notifications");
    const ws = useRef<WebSocket | null>(null);
    const reconnectAttempts = useRef(0);
    const reconnectTimeout = useRef<NodeJS.Timeout | null>(null);
    const heartbeatInterval = useRef<NodeJS.Timeout | null>(null);

    const [isConnected, setIsConnected] = useState(false);
    const [notifications, setNotifications] = useState<Notification[]>([]);

    const clearNotifications = useCallback(() => {
        setNotifications([]);
    }, []);

    const sendMessage = useCallback((message: unknown) => {
        if (ws.current && ws.current.readyState === WebSocket.OPEN) {
            ws.current.send(JSON.stringify(message));
        }
    }, []);

    const handleMessage = useCallback(
        (event: MessageEvent) => {
            try {
                const notification: Notification = JSON.parse(event.data);

                // Skip pong messages
                if (notification.type === "pong") {
                    return;
                }

                // Add to notifications list (keep last 50)
                setNotifications((prev) => [notification, ...prev].slice(0, 50));

                // Show toast based on notification type
                const toastVariant = getToastVariant(notification.type);
                const title = getToastTitle(notification.type, t);

                toast({
                    title,
                    description: notification.message,
                    variant: toastVariant,
                });

                // Invalidate relevant queries based on notification type
                if (notification.type.startsWith("record_") || notification.type.startsWith("batch_")) {
                    queryClient.invalidateQueries({ queryKey: ["records"] });
                    queryClient.invalidateQueries({ queryKey: ["stats"] });
                }

                if (notification.type === "export_complete" || notification.type === "sheets_sync_complete") {
                    queryClient.invalidateQueries({ queryKey: ["records"] });
                }
            } catch (error) {
                console.error("Failed to parse notification:", error);
            }
        },
        [toast, queryClient, t]
    );

    const connect = useCallback(() => {
        if (!enabled) return;

        // Don't try to connect if we've exhausted retry attempts
        if (reconnectAttempts.current >= maxReconnectAttempts) {
            return;
        }

        try {
            ws.current = new WebSocket(WS_URL);

            ws.current.onopen = () => {
                setIsConnected(true);
                reconnectAttempts.current = 0;
                if (process.env.NODE_ENV === "development") {
                    console.log("WebSocket connected");
                }

                // Start heartbeat
                heartbeatInterval.current = setInterval(() => {
                    sendMessage({ type: "ping", timestamp: new Date().toISOString() });
                }, 30000);
            };

            ws.current.onmessage = handleMessage;

            ws.current.onclose = () => {
                setIsConnected(false);

                // Clear heartbeat
                if (heartbeatInterval.current) {
                    clearInterval(heartbeatInterval.current);
                    heartbeatInterval.current = null;
                }

                // Attempt reconnection silently
                if (autoReconnect && reconnectAttempts.current < maxReconnectAttempts) {
                    reconnectAttempts.current += 1;
                    reconnectTimeout.current = setTimeout(connect, reconnectInterval);
                }
            };

            ws.current.onerror = () => {
                // Silently handle errors - connection failures are expected when backend is down
                // The onclose handler will take care of reconnection attempts
            };
        } catch {
            // Silently handle connection errors
        }
    }, [enabled, autoReconnect, maxReconnectAttempts, reconnectInterval, handleMessage, sendMessage]);

    useEffect(() => {
        connect();

        return () => {
            if (reconnectTimeout.current) {
                clearTimeout(reconnectTimeout.current);
            }
            if (heartbeatInterval.current) {
                clearInterval(heartbeatInterval.current);
            }
            if (ws.current) {
                ws.current.close();
            }
        };
    }, [connect]);

    return {
        isConnected,
        notifications,
        clearNotifications,
        sendMessage,
    };
}

function getToastVariant(
    type: string
): "default" | "destructive" | undefined {
    switch (type) {
        case "error":
        case "record_rejected":
            return "destructive";
        default:
            return "default";
    }
}

function getToastTitle(type: string, t: (key: string) => string): string {
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
