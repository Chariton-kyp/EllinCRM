"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  MessageCircle,
  Sparkles,
  X,
  Send,
  Square,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { MessageBubble } from "./message-bubble";
import { SourceCitation } from "./source-citation";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
}

interface Source {
  record_id: string;
  source_file: string;
  record_type: string;
  score: number;
}

// Phase 2A: structured tool call lifecycle event from the LangGraph agent.
// Each assistant message may have 0-N tool events attached (displayed as chips).
export interface ToolEvent {
  id: string; // run_id from LangGraph
  name: string; // canonical tool name (count_records, etc.)
  displayEl: string; // Greek display label
  status: "running" | "done" | "error";
  summaryEl?: string; // short Greek result summary (shown on resolved chip)
}

const THREAD_ID_STORAGE_KEY = "ellincrm_chat_thread_id";

const SUGGESTION_QUESTIONS = [
  "\u03A0\u03BF\u03B9\u03B1 \u03C4\u03B9\u03BC\u03BF\u03BB\u03BF\u03B3\u03B9\u03B1 \u03BE\u03B5\u03C0\u03B5\u03C1\u03BD\u03BF\u03C5\u03BD \u03C4\u03B1 1000EUR;",
  "\u03A0\u03BF\u03B9\u03BF\u03C2 \u03C0\u03B5\u03BB\u03B1\u03C4\u03B7\u03C2 \u03B6\u03B7\u03C4\u03B7\u03C3\u03B5 \u03C5\u03C0\u03B7\u03C1\u03B5\u03C3\u03B9\u03B5\u03C2 CRM;",
  "\u0394\u03B5\u03B9\u03BE\u03B5 \u03BC\u03BF\u03C5 \u03C4\u03B1 email \u03B1\u03C0\u03BF \u03B4\u03B9\u03BA\u03B7\u03B3\u03BF\u03C1\u03B9\u03BA\u03B1 \u03B3\u03C1\u03B1\u03C6\u03B5\u03B9\u03B1",
  "\u03A0\u03BF\u03B9\u03BF \u03B5\u03B9\u03BD\u03B1\u03B9 \u03C4\u03BF \u03C3\u03C5\u03BD\u03BF\u03BB\u03B9\u03BA\u03BF \u03C0\u03BF\u03C3\u03BF \u03C4\u03B9\u03BC\u03BF\u03BB\u03BF\u03B3\u03B9\u03C9\u03BD;",
  "\u03A0\u03BF\u03B9\u03B5\u03C2 \u03C6\u03BF\u03C1\u03BC\u03B5\u03C2 \u03B5\u03C7\u03BF\u03C5\u03BD \u03C5\u03C8\u03B7\u03BB\u03B7 \u03C0\u03C1\u03BF\u03C4\u03B5\u03C1\u03B1\u03B9\u03BF\u03C4\u03B7\u03C4\u03B1;",
];

const API_URL =
  (process.env.NEXT_PUBLIC_API_URL || "http://localhost:7000") + "/api/v1/chat";

function generateId() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
}

export function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [sources, setSources] = useState<Record<string, Source[]>>({});
  // Phase 2A: tool call events per assistant message (rendered as chips)
  const [toolEvents, setToolEvents] = useState<Record<string, ToolEvent[]>>({});
  // Phase 2C: conversation thread id persisted in localStorage for follow-ups
  const [threadId, setThreadId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Hydrate thread_id from localStorage on first mount
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const stored = window.localStorage.getItem(THREAD_ID_STORAGE_KEY);
      if (stored) setThreadId(stored);
    } catch {
      // localStorage unavailable (private mode); start fresh
    }
  }, []);

  // Auto-scroll on new messages or streaming updates
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isStreaming]);

  // Focus input when panel opens
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 300);
    }
  }, [isOpen]);

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || isStreaming) return;

      const userMsg: ChatMessage = {
        id: generateId(),
        role: "user",
        content: trimmed,
      };
      const assistantId = generateId();

      setMessages((prev) => [...prev, userMsg]);
      setInput("");
      setIsStreaming(true);

      // Build message history for API
      const apiMessages = [...messages, userMsg].map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const abortController = new AbortController();
      abortRef.current = abortController;

      try {
        const response = await fetch(API_URL, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            messages: apiMessages,
            stream: true,
            thread_id: threadId,
          }),
          signal: abortController.signal,
        });

        if (!response.ok) {
          throw new Error(`Server error: ${response.status}`);
        }

        const reader = response.body?.getReader();
        if (!reader) throw new Error("No response body");

        const decoder = new TextDecoder();
        let buffer = "";
        let assistantCreated = false;

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const events = buffer.split("\n\n");
          // Keep incomplete last chunk in buffer
          buffer = events.pop() || "";

          for (const event of events) {
            const dataLine = event
              .split("\n")
              .find((line) => line.startsWith("data: "));
            if (!dataLine) continue;

            const jsonStr = dataLine.slice(6); // Remove "data: " prefix
            if (!jsonStr.trim()) continue;

            try {
              const data = JSON.parse(jsonStr);

              if (data.type === "token" && data.content) {
                if (!assistantCreated) {
                  setMessages((prev) => [
                    ...prev,
                    { id: assistantId, role: "assistant", content: data.content },
                  ]);
                  assistantCreated = true;
                } else {
                  setMessages((prev) =>
                    prev.map((m) =>
                      m.id === assistantId
                        ? { ...m, content: m.content + data.content }
                        : m
                    )
                  );
                }
              } else if (data.type === "tool_call_start") {
                // Create the assistant message stub if needed so chips
                // can render above any future text tokens.
                if (!assistantCreated) {
                  setMessages((prev) => [
                    ...prev,
                    { id: assistantId, role: "assistant", content: "" },
                  ]);
                  assistantCreated = true;
                }
                setToolEvents((prev) => {
                  const existing = prev[assistantId] || [];
                  return {
                    ...prev,
                    [assistantId]: [
                      ...existing,
                      {
                        id: data.id,
                        name: data.name,
                        displayEl: data.display_el,
                        status: "running",
                      },
                    ],
                  };
                });
              } else if (data.type === "tool_call_result") {
                setToolEvents((prev) => {
                  const existing = prev[assistantId] || [];
                  return {
                    ...prev,
                    [assistantId]: existing.map((ev) =>
                      ev.id === data.id
                        ? {
                            ...ev,
                            status: data.ok ? "done" : "error",
                            summaryEl: data.summary_el,
                          }
                        : ev
                    ),
                  };
                });
              } else if (data.type === "status") {
                // Lightweight status updates; currently unused in UI but kept
                // for future loading indicators.
              } else if (data.type === "sources" && data.sources) {
                setSources((prev) => ({
                  ...prev,
                  [assistantId]: data.sources,
                }));
              } else if (data.type === "done") {
                // Persist thread_id for follow-up questions (Phase 2C)
                if (data.thread_id && typeof window !== "undefined") {
                  try {
                    window.localStorage.setItem(
                      THREAD_ID_STORAGE_KEY,
                      data.thread_id,
                    );
                    setThreadId(data.thread_id);
                  } catch {
                    // localStorage unavailable; thread_id won't persist across reload
                  }
                }
              } else if (data.type === "error") {
                if (!assistantCreated) {
                  setMessages((prev) => [
                    ...prev,
                    {
                      id: assistantId,
                      role: "assistant",
                      content: data.content || "An error occurred.",
                    },
                  ]);
                }
              }
            } catch {
              // Ignore malformed JSON chunks
            }
          }
        }
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === "AbortError") {
          // User cancelled, ignore
        } else {
          const errorMsg =
            err instanceof Error ? err.message : "Connection failed";
          setMessages((prev) => [
            ...prev,
            {
              id: assistantId,
              role: "assistant",
              content: `Error: ${errorMsg}. Please check that the backend is running.`,
            },
          ]);
        }
      } finally {
        setIsStreaming(false);
        abortRef.current = null;
      }
    },
    [messages, isStreaming, threadId]
  );

  const handleStop = () => {
    abortRef.current?.abort();
    setIsStreaming(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  const isEmpty = messages.length === 0;

  return (
    <>
      {/* FAB Button */}
      <motion.button
        onClick={() => setIsOpen((prev) => !prev)}
        className={cn(
          "fixed bottom-4 right-4 z-50 w-14 h-14 rounded-full",
          "bg-gradient-to-br from-sky-400 to-sky-600 text-white",
          "shadow-lg hover:shadow-xl transition-shadow",
          "flex items-center justify-center"
        )}
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        animate={
          isEmpty && !isOpen
            ? { scale: [1, 1.08, 1], boxShadow: ["0 10px 15px -3px rgba(0,0,0,0.1)", "0 10px 25px -3px rgba(14,165,233,0.4)", "0 10px 15px -3px rgba(0,0,0,0.1)"] }
            : {}
        }
        transition={
          isEmpty && !isOpen
            ? { duration: 2, repeat: Infinity, ease: "easeInOut" }
            : { duration: 0.15 }
        }
      >
        <AnimatePresence mode="wait">
          {isOpen ? (
            <motion.div
              key="close"
              initial={{ rotate: -90, opacity: 0 }}
              animate={{ rotate: 0, opacity: 1 }}
              exit={{ rotate: 90, opacity: 0 }}
              transition={{ duration: 0.15 }}
            >
              <X className="w-6 h-6" />
            </motion.div>
          ) : (
            <motion.div
              key="open"
              initial={{ rotate: 90, opacity: 0 }}
              animate={{ rotate: 0, opacity: 1 }}
              exit={{ rotate: -90, opacity: 0 }}
              transition={{ duration: 0.15 }}
            >
              <MessageCircle className="w-6 h-6" />
            </motion.div>
          )}
        </AnimatePresence>
      </motion.button>

      {/* Chat Panel */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            transition={{ duration: 0.2 }}
            className={cn(
              "fixed bottom-20 right-4 z-50",
              "w-[380px] h-[520px] max-h-[80vh]",
              "rounded-2xl border border-gray-200 dark:border-gray-700",
              "bg-white dark:bg-gray-900 shadow-2xl",
              "flex flex-col overflow-hidden"
            )}
          >
            {/* Header */}
            <div className="flex items-center gap-3 px-4 py-3 bg-gradient-to-r from-sky-500 to-sky-600 text-white">
              <Sparkles className="w-5 h-5 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <h3 className="font-semibold text-sm leading-tight">
                  AI {"\u0392\u03BF\u03B7\u03B8\u03BF\u03C2"} EllinCRM
                </h3>
                <p className="text-xs text-sky-100 leading-tight">
                  Claude Sonnet
                </p>
              </div>
              <button
                onClick={() => setIsOpen(false)}
                className="p-1 hover:bg-white/20 rounded transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto px-3 py-3">
              {isEmpty ? (
                <div className="flex flex-col items-center justify-center h-full text-center px-4">
                  <div className="w-12 h-12 rounded-full bg-sky-100 dark:bg-sky-900 flex items-center justify-center mb-3">
                    <Sparkles className="w-6 h-6 text-sky-500" />
                  </div>
                  <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    {"\u0393\u03B5\u03B9\u03B1 \u03C3\u03B1\u03C2! \u03A0\u03C9\u03C2 \u03BC\u03C0\u03BF\u03C1\u03C9 \u03BD\u03B1 \u03C3\u03B1\u03C2 \u03B2\u03BF\u03B7\u03B8\u03B7\u03C3\u03C9;"}
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mb-4">
                    {"\u0394\u03BF\u03BA\u03B9\u03BC\u03B1\u03C3\u03C4\u03B5 \u03BC\u03B9\u03B1 \u03B1\u03C0\u03BF \u03C4\u03B9\u03C2 \u03C0\u03C1\u03BF\u03C4\u03B5\u03B9\u03BD\u03BF\u03BC\u03B5\u03BD\u03B5\u03C2 \u03B5\u03C1\u03C9\u03C4\u03B7\u03C3\u03B5\u03B9\u03C2:"}
                  </p>
                  <div className="flex flex-wrap justify-center gap-2">
                    {SUGGESTION_QUESTIONS.map((q) => (
                      <button
                        key={q}
                        onClick={() => sendMessage(q)}
                        className={cn(
                          "text-xs px-3 py-1.5 rounded-full",
                          "border border-gray-200 dark:border-gray-700",
                          "text-gray-600 dark:text-gray-400",
                          "hover:bg-sky-50 hover:border-sky-300 hover:text-sky-600",
                          "dark:hover:bg-sky-950 dark:hover:border-sky-700 dark:hover:text-sky-400",
                          "transition-colors"
                        )}
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <>
                  {messages.map((msg, idx) => (
                    <div key={msg.id}>
                      <MessageBubble
                        role={msg.role}
                        content={msg.content}
                        isStreaming={
                          isStreaming &&
                          msg.role === "assistant" &&
                          idx === messages.length - 1
                        }
                        toolEvents={
                          msg.role === "assistant" ? toolEvents[msg.id] : undefined
                        }
                      />
                      {msg.role === "assistant" &&
                        sources[msg.id] &&
                        !(
                          isStreaming && idx === messages.length - 1
                        ) && <SourceCitation sources={sources[msg.id]} />}
                    </div>
                  ))}
                  {/* Streaming indicator: bouncing dots when waiting for first token */}
                  {isStreaming &&
                    messages[messages.length - 1]?.role === "user" && (
                      <div className="flex gap-1 ml-9 mt-2">
                        {[0, 1, 2].map((i) => (
                          <motion.div
                            key={i}
                            className="w-2 h-2 rounded-full bg-sky-400"
                            animate={{ y: [0, -6, 0] }}
                            transition={{
                              duration: 0.6,
                              repeat: Infinity,
                              delay: i * 0.15,
                            }}
                          />
                        ))}
                      </div>
                    )}
                  <div ref={messagesEndRef} />
                </>
              )}
            </div>

            {/* Input Area */}
            <div className="border-t border-gray-200 dark:border-gray-700 px-3 py-2 flex items-end gap-2">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={"\u0393\u03C1\u03B1\u03C8\u03C4\u03B5 \u03BC\u03B7\u03BD\u03C5\u03BC\u03B1..."}
                rows={1}
                className={cn(
                  "flex-1 resize-none text-sm py-2 px-3 rounded-xl",
                  "bg-gray-100 dark:bg-gray-800",
                  "border-0 outline-none focus:ring-2 focus:ring-sky-400",
                  "placeholder:text-gray-400 dark:placeholder:text-gray-500",
                  "text-gray-800 dark:text-gray-200"
                )}
              />
              {isStreaming ? (
                <button
                  onClick={handleStop}
                  className="p-2 rounded-xl bg-red-500 text-white hover:bg-red-600 transition-colors"
                >
                  <Square className="w-4 h-4" />
                </button>
              ) : (
                <button
                  onClick={() => sendMessage(input)}
                  disabled={!input.trim()}
                  className={cn(
                    "p-2 rounded-xl transition-colors",
                    input.trim()
                      ? "bg-sky-500 text-white hover:bg-sky-600"
                      : "bg-gray-200 text-gray-400 dark:bg-gray-700 dark:text-gray-500"
                  )}
                >
                  <Send className="w-4 h-4" />
                </button>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
