"use client";

import { motion } from "framer-motion";
import { User, Bot } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ComponentPropsWithoutRef } from "react";
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
        {isUser ? (
          <span className="whitespace-pre-wrap break-words">{content}</span>
        ) : (
          <div
            className={cn(
              "prose prose-sm dark:prose-invert max-w-none break-words",
              "prose-p:my-1 prose-headings:my-2 prose-headings:font-semibold",
              "prose-ul:my-1 prose-ol:my-1 prose-li:my-0",
              "prose-table:my-2 prose-hr:my-2",
              "prose-pre:my-2 prose-pre:bg-gray-200 dark:prose-pre:bg-gray-900",
              "prose-code:before:content-none prose-code:after:content-none"
            )}
          >
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                a: ({ ...props }: ComponentPropsWithoutRef<"a">) => (
                  <a
                    {...props}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sky-600 dark:text-sky-400 underline"
                  />
                ),
                table: ({ ...props }: ComponentPropsWithoutRef<"table">) => (
                  <div className="overflow-x-auto">
                    <table
                      {...props}
                      className="border-collapse border border-gray-300 dark:border-gray-700 text-xs"
                    />
                  </div>
                ),
                th: ({ ...props }: ComponentPropsWithoutRef<"th">) => (
                  <th
                    {...props}
                    className="border border-gray-300 dark:border-gray-700 px-2 py-1 bg-gray-200 dark:bg-gray-900 font-semibold text-left"
                  />
                ),
                td: ({ ...props }: ComponentPropsWithoutRef<"td">) => (
                  <td
                    {...props}
                    className="border border-gray-300 dark:border-gray-700 px-2 py-1"
                  />
                ),
                code: ({
                  className,
                  children,
                  ...props
                }: ComponentPropsWithoutRef<"code"> & { inline?: boolean }) => {
                  const isBlock = /\n/.test(String(children ?? "")) || /language-/.test(className ?? "");
                  if (isBlock) {
                    return (
                      <code
                        {...props}
                        className={cn(
                          className,
                          "block rounded px-2 py-1 bg-gray-200 dark:bg-gray-900 text-xs font-mono overflow-x-auto"
                        )}
                      >
                        {children}
                      </code>
                    );
                  }
                  return (
                    <code
                      {...props}
                      className="rounded px-1 py-0.5 bg-gray-200 dark:bg-gray-900 text-xs font-mono"
                    >
                      {children}
                    </code>
                  );
                },
              }}
            >
              {content}
            </ReactMarkdown>
          </div>
        )}
        {isStreaming && (
          <span className="inline-block w-1.5 h-4 ml-0.5 bg-current animate-pulse rounded-sm align-text-bottom" />
        )}
      </div>
    </motion.div>
  );
}
