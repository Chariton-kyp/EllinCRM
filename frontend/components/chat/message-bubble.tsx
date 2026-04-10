"use client";

import { motion, AnimatePresence } from "framer-motion";
import { User, Bot, Loader2, CheckCircle2, XCircle } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";

// Phase 2A: structured tool call lifecycle events rendered as chips above
// the assistant text. Kept internal to avoid a cross-file type dependency.
interface ToolEvent {
  id: string;
  name: string;
  displayEl: string;
  status: "running" | "done" | "error";
  summaryEl?: string;
}

interface MessageBubbleProps {
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
  /** Phase 2A: tool call lifecycle events shown as chips above assistant text */
  toolEvents?: ToolEvent[];
}

function ToolChips({ events }: { events: ToolEvent[] }) {
  if (!events || events.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1.5 mb-2">
      <AnimatePresence initial={false}>
        {events.map((ev) => (
          <motion.div
            key={ev.id}
            initial={{ opacity: 0, scale: 0.9, y: -4 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9 }}
            transition={{ duration: 0.15 }}
            className={cn(
              "inline-flex items-center gap-1.5 text-xs px-2 py-0.5 rounded-full",
              "border transition-colors",
              ev.status === "running" &&
                "bg-sky-50 dark:bg-sky-950/40 border-sky-200 dark:border-sky-800 text-sky-700 dark:text-sky-300",
              ev.status === "done" &&
                "bg-emerald-50 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-800 text-emerald-700 dark:text-emerald-300",
              ev.status === "error" &&
                "bg-red-50 dark:bg-red-950/40 border-red-200 dark:border-red-800 text-red-700 dark:text-red-300",
            )}
            title={ev.summaryEl ? `${ev.displayEl}: ${ev.summaryEl}` : ev.displayEl}
          >
            {ev.status === "running" && (
              <Loader2 className="w-3 h-3 animate-spin flex-shrink-0" />
            )}
            {ev.status === "done" && (
              <CheckCircle2 className="w-3 h-3 flex-shrink-0" />
            )}
            {ev.status === "error" && (
              <XCircle className="w-3 h-3 flex-shrink-0" />
            )}
            <span className="truncate max-w-[180px]">
              {ev.displayEl}
              {ev.status === "done" && ev.summaryEl && (
                <span className="ml-1 opacity-75">· {ev.summaryEl}</span>
              )}
            </span>
          </motion.div>
        ))}
      </AnimatePresence>
      {events.some(ev => ev.status === "error") && (
        <p className="text-xs text-red-500 dark:text-red-400 mt-1 italic">
          Ένα ή περισσότερα εργαλεία απέτυχαν. Η απάντηση μπορεί να είναι ελλιπής.
        </p>
      )}
    </div>
  );
}

export function MessageBubble({
  role,
  content,
  isStreaming,
  toolEvents,
}: MessageBubbleProps) {
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
            <ToolChips events={toolEvents || []} />
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                a: ({ node: _, ...props }: any) => (
                  <a
                    {...props}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sky-600 dark:text-sky-400 underline"
                  />
                ),
                table: ({ node: _, ...props }: any) => (
                  <div className="overflow-x-auto">
                    <table
                      {...props}
                      className="border-collapse border border-gray-300 dark:border-gray-700 text-xs"
                    />
                  </div>
                ),
                th: ({ node: _, ...props }: any) => (
                  <th
                    {...props}
                    className="border border-gray-300 dark:border-gray-700 px-2 py-1 bg-gray-200 dark:bg-gray-900 font-semibold text-left"
                  />
                ),
                td: ({ node: _, ...props }: any) => (
                  <td
                    {...props}
                    className="border border-gray-300 dark:border-gray-700 px-2 py-1"
                  />
                ),
                code: ({
                  node: _,
                  className,
                  children,
                  ...props
                }: any) => {
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
