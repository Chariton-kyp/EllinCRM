"use client";

import { useEffect, useState } from "react";

interface ServiceWorkerState {
  isSupported: boolean;
  isRegistered: boolean;
  isOnline: boolean;
  registration: ServiceWorkerRegistration | null;
}

/**
 * Hook to manage Service Worker registration and state.
 *
 * Registers the service worker on mount and tracks its state.
 * Also monitors online/offline status.
 */
export function useServiceWorker(): ServiceWorkerState {
  const [state, setState] = useState<ServiceWorkerState>({
    isSupported: false,
    isRegistered: false,
    isOnline: true,
    registration: null,
  });

  useEffect(() => {
    // Check if running in browser
    if (typeof window === "undefined") {
      return;
    }

    // Check service worker support
    const isSupported = "serviceWorker" in navigator;
    setState((prev) => ({ ...prev, isSupported }));

    if (!isSupported) {
      console.log("[PWA] Service Workers not supported");
      return;
    }

    // Register service worker
    const registerSW = async () => {
      try {
        const registration = await navigator.serviceWorker.register("/sw.js", {
          scope: "/",
        });

        console.log("[PWA] Service Worker registered:", registration.scope);

        setState((prev) => ({
          ...prev,
          isRegistered: true,
          registration,
        }));

        // Check for updates
        registration.addEventListener("updatefound", () => {
          const newWorker = registration.installing;
          if (newWorker) {
            newWorker.addEventListener("statechange", () => {
              if (
                newWorker.state === "installed" &&
                navigator.serviceWorker.controller
              ) {
                // New content available
                console.log("[PWA] New content available");
              }
            });
          }
        });
      } catch (error) {
        console.error("[PWA] Service Worker registration failed:", error);
      }
    };

    // Register when ready
    if (document.readyState === "complete") {
      registerSW();
    } else {
      window.addEventListener("load", registerSW);
    }

    // Monitor online status
    const updateOnlineStatus = () => {
      setState((prev) => ({ ...prev, isOnline: navigator.onLine }));
    };

    window.addEventListener("online", updateOnlineStatus);
    window.addEventListener("offline", updateOnlineStatus);

    // Set initial online status
    updateOnlineStatus();

    return () => {
      window.removeEventListener("online", updateOnlineStatus);
      window.removeEventListener("offline", updateOnlineStatus);
    };
  }, []);

  return state;
}

/**
 * Request push notification permission.
 */
export async function requestNotificationPermission(): Promise<boolean> {
  if (!("Notification" in window)) {
    console.log("[PWA] Notifications not supported");
    return false;
  }

  if (Notification.permission === "granted") {
    return true;
  }

  if (Notification.permission === "denied") {
    console.log("[PWA] Notifications denied");
    return false;
  }

  const permission = await Notification.requestPermission();
  return permission === "granted";
}

/**
 * Subscribe to push notifications.
 */
export async function subscribeToPush(
  registration: ServiceWorkerRegistration,
  vapidPublicKey?: string
): Promise<PushSubscription | null> {
  try {
    const subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: vapidPublicKey,
    });

    console.log("[PWA] Push subscription:", subscription);
    return subscription;
  } catch (error) {
    console.error("[PWA] Push subscription failed:", error);
    return null;
  }
}
