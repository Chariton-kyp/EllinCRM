"use client";

import { useState, useCallback, useRef } from "react";
import { Upload, FileText, Mail, Receipt, X, FolderUp } from "lucide-react";
import { cn } from "@/lib/utils";

interface QueuedFile {
  file: File;
  type: "form" | "email" | "invoice" | "unknown";
  icon: typeof FileText;
}

function detectFileType(file: File): QueuedFile["type"] {
  const name = file.name.toLowerCase();
  if (name.endsWith(".eml")) return "email";
  if (name.includes("invoice") || name.startsWith("inv")) return "invoice";
  if (name.includes("form") || name.startsWith("contact")) return "form";
  if (name.endsWith(".html")) return "form";
  return "unknown";
}

function getFileIcon(type: QueuedFile["type"]) {
  switch (type) {
    case "form":
      return FileText;
    case "email":
      return Mail;
    case "invoice":
      return Receipt;
    default:
      return FileText;
  }
}

function getTypeLabel(type: QueuedFile["type"]): string {
  switch (type) {
    case "form":
      return "Form";
    case "email":
      return "Email";
    case "invoice":
      return "Invoice";
    default:
      return "File";
  }
}

export function DragDropUpload() {
  const [isDragOver, setIsDragOver] = useState(false);
  const [queuedFiles, setQueuedFiles] = useState<QueuedFile[]>([]);
  const dragCounterRef = useRef(0);

  const handleFiles = useCallback((files: FileList | null) => {
    if (!files || files.length === 0) return;

    const newFiles: QueuedFile[] = Array.from(files).map((file) => {
      const type = detectFileType(file);
      return { file, type, icon: getFileIcon(type) };
    });

    setQueuedFiles((prev) => [...prev, ...newFiles]);
  }, []);

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current++;
    if (e.dataTransfer.items && e.dataTransfer.items.length > 0) {
      setIsDragOver(true);
    }
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current--;
    if (dragCounterRef.current === 0) {
      setIsDragOver(false);
    }
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragOver(false);
      dragCounterRef.current = 0;
      handleFiles(e.dataTransfer.files);
    },
    [handleFiles]
  );

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      handleFiles(e.target.files);
      // Reset input so the same file can be selected again
      e.target.value = "";
    },
    [handleFiles]
  );

  const removeFile = useCallback((index: number) => {
    setQueuedFiles((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const clearAll = useCallback(() => {
    setQueuedFiles([]);
  }, []);

  return (
    <div className="space-y-3">
      {/* Drop Zone — file input overlays the entire zone so clicks hit it directly */}
      <div
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        className={cn(
          "relative flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 transition-all duration-200",
          isDragOver
            ? "border-blue-500 bg-blue-50 dark:bg-blue-950/30"
            : "border-muted-foreground/25 hover:border-muted-foreground/50 hover:bg-muted/50"
        )}
      >
        {/* Invisible file input covering the entire drop zone — user clicks it directly */}
        <input
          type="file"
          multiple
          accept=".html,.eml,.pdf"
          onChange={handleFileInput}
          className="absolute inset-0 z-10 h-full w-full cursor-pointer opacity-0"
        />

        <div
          className={cn(
            "mb-3 rounded-full p-3 transition-colors",
            isDragOver ? "bg-blue-100 dark:bg-blue-900/50" : "bg-muted"
          )}
        >
          {isDragOver ? (
            <FolderUp className="h-6 w-6 text-blue-600 dark:text-blue-400" />
          ) : (
            <Upload className="h-6 w-6 text-muted-foreground" />
          )}
        </div>

        <p className={cn(
          "text-sm font-medium",
          isDragOver ? "text-blue-600 dark:text-blue-400" : "text-muted-foreground"
        )}>
          {isDragOver
            ? "Drop files here"
            : "Drag and drop files here, or click to browse"}
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          Supports HTML forms, EML emails, HTML/PDF invoices
        </p>
      </div>

      {/* Queued Files List */}
      {queuedFiles.length > 0 && (
        <div className="rounded-lg border bg-muted/30 p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-medium">
              {queuedFiles.length} file{queuedFiles.length !== 1 ? "s" : ""} queued
            </span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                clearAll();
              }}
              className="text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              Clear all
            </button>
          </div>
          <div className="space-y-1.5">
            {queuedFiles.map((qf, index) => {
              const Icon = qf.icon;
              return (
                <div
                  key={`${qf.file.name}-${index}`}
                  className="flex items-center gap-2 rounded-md bg-background px-3 py-2 text-sm"
                >
                  <Icon className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <span className="flex-1 truncate">{qf.file.name}</span>
                  <span className="shrink-0 rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
                    {getTypeLabel(qf.type)}
                  </span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      removeFile(index);
                    }}
                    className="shrink-0 text-muted-foreground hover:text-foreground transition-colors"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              );
            })}
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            Files are processed from the server&apos;s data directory. Use the file browser below to extract.
          </p>
        </div>
      )}
    </div>
  );
}
