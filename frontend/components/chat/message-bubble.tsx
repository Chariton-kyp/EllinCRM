"use client";

import { motion } from "framer-motion";
import { User, Bot } from "lucide-react";
import { cn } from "@/lib/utils";

interface MessageBubbleProps {
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
}

export function MessageBubble({ role, content, isStreaming }: MessageBubbleProps) {
  const isUser = role === "user";

  return (
    <motion.div
      initial={{ opacity: 0, x: isUser ? 20 : -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.2 }}
      className={cn("flex gap-2 mb-3", isUser ? "flex-row-reverse" : "flex-row")}
    >
      <div
        className={cn(
          "flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center",
          isUser
            ? "bg-sky-500 text-white"
            : "bg-gray-200 text-gray-600 dark:bg-gray-700 dark:text-gray-300"
        )}
      >
        {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
      </div>
      <div
        className={cn(
          "max-w-[80%] px-3 py-2 rounded-2xl text-sm leading-relaxed",
          isUser
            ? "bg-sky-500 text-white rounded-br-md"
            : "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200 rounded-bl-md"
        )}
      >
        <span className="whitespace-pre-wrap break-words">{content}</span>
        {isStreaming && (
          <span className="inline-block w-1.5 h-4 ml-0.5 bg-current animate-pulse rounded-sm align-text-bottom" />
        )}
      </div>
    </motion.div>
  );
}
