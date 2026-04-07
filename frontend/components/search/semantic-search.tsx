"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import {
  Search,
  Loader2,
  FileText,
  Mail,
  Receipt,
  Sparkles,
  X,
  ChevronRight,
  RefreshCw,
  AlertCircle,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { StatusBadge } from "@/components/records/status-badge";
import {
  searchRecords,
  getEmbeddingStats,
  generateEmbeddings,
  type SearchResult,
  type SearchResponse,
} from "@/lib/api/search";
import { useDebounce } from "@/lib/hooks/use-debounce";
import { cn } from "@/lib/utils";
import Link from "next/link";

// Session storage keys
const SEARCH_STATE_KEY = "ellincrm_search_state";
const NAVIGATED_TO_RESULT_KEY = "ellincrm_navigated_to_result";

interface SavedSearchState {
  query: string;
  recordType: string;
  status: string;
  isExpanded: boolean;
  results: SearchResponse | null;
}

interface SemanticSearchProps {
  onResultClick?: (recordId: string) => void;
  className?: string;
}

export function SemanticSearch({ onResultClick, className }: SemanticSearchProps) {
  const [query, setQuery] = useState("");
  const [recordType, setRecordType] = useState<string>("all");
  const [status, setStatus] = useState<string>("all");
  const [isExpanded, setIsExpanded] = useState(false);
  const [savedResults, setSavedResults] = useState<SearchResponse | null>(null);
  const [isInitialized, setIsInitialized] = useState(false);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const t = useTranslations("search");
  const tType = useTranslations("type");
  const tStatus = useTranslations("status");

  const debouncedQuery = useDebounce(query, 300);

  // Listen for Ctrl+K "open-search" and Escape "close-panels" custom events
  useEffect(() => {
    function handleOpenSearch() {
      searchInputRef.current?.focus();
      searchInputRef.current?.select();
    }
    function handleClosePanels() {
      setIsExpanded(false);
    }
    window.addEventListener("open-search", handleOpenSearch);
    window.addEventListener("close-panels", handleClosePanels);
    return () => {
      window.removeEventListener("open-search", handleOpenSearch);
      window.removeEventListener("close-panels", handleClosePanels);
    };
  }, []);

  // Restore search state from sessionStorage on mount
  // Only restore if we navigated to a search result and came back
  useEffect(() => {
    if (typeof window !== "undefined") {
      const navigatedToResult = sessionStorage.getItem(NAVIGATED_TO_RESULT_KEY);

      if (navigatedToResult === "true") {
        // Coming back from a search result - restore state
        try {
          const saved = sessionStorage.getItem(SEARCH_STATE_KEY);
          if (saved) {
            const state: SavedSearchState = JSON.parse(saved);
            setQuery(state.query);
            setRecordType(state.recordType);
            setStatus(state.status);
            setIsExpanded(state.isExpanded);
            setSavedResults(state.results);
          }
        } catch (e) {
          // Ignore parse errors
        }
        // Clear the navigation flag - next navigation from elsewhere won't restore
        sessionStorage.removeItem(NAVIGATED_TO_RESULT_KEY);
      } else {
        // Not coming from a search result - clear any saved state
        sessionStorage.removeItem(SEARCH_STATE_KEY);
      }
      setIsInitialized(true);
    }
  }, []);

  // Save search state to sessionStorage when it changes
  useEffect(() => {
    if (typeof window !== "undefined" && isInitialized && savedResults) {
      const state: SavedSearchState = {
        query,
        recordType,
        status,
        isExpanded,
        results: savedResults,
      };
      sessionStorage.setItem(SEARCH_STATE_KEY, JSON.stringify(state));
    }
  }, [query, recordType, status, isExpanded, savedResults, isInitialized]);

  // Fetch embedding stats to check if embeddings exist
  const { data: embeddingStats, refetch: refetchStats } = useQuery({
    queryKey: ["embeddingStats"],
    queryFn: getEmbeddingStats,
    refetchOnWindowFocus: false,
  });

  const searchMutation = useMutation({
    mutationFn: searchRecords,
    onSuccess: (data) => {
      setSavedResults(data);
    },
  });

  const generateMutation = useMutation({
    mutationFn: () => generateEmbeddings(),
    onSuccess: () => {
      refetchStats();
    },
  });

  const handleSearch = useCallback(() => {
    if (!query.trim()) return;

    searchMutation.mutate({
      query: query.trim(),
      limit: 10,
      min_similarity: 0.3,  // Hybrid search threshold: keyword matches boost score above this
      record_type: recordType === "all" ? undefined : recordType,
      status: status === "all" ? undefined : status,
    });
    setIsExpanded(true);
  }, [query, recordType, status, searchMutation]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleSearch();
    }
    if (e.key === "Escape") {
      setIsExpanded(false);
    }
  };

  const handleClear = () => {
    setQuery("");
    setIsExpanded(false);
    setSavedResults(null);
    searchMutation.reset();
    // Clear from session storage
    if (typeof window !== "undefined") {
      sessionStorage.removeItem(SEARCH_STATE_KEY);
    }
  };

  // Use saved results when mutation data is not available
  const displayResults = searchMutation.data || savedResults;

  const getRecordIcon = (type: string) => {
    switch (type) {
      case "FORM":
        return <FileText className="h-4 w-4 text-blue-500" />;
      case "EMAIL":
        return <Mail className="h-4 w-4 text-purple-500" />;
      case "INVOICE":
        return <Receipt className="h-4 w-4 text-green-500" />;
      default:
        return <FileText className="h-4 w-4" />;
    }
  };

  const formatSimilarity = (score: number) => {
    return `${Math.round(score * 100)}%`;
  };

  const hasRecordsWithoutEmbeddings = embeddingStats && embeddingStats.records_without_embeddings > 0;
  const hasAnyEmbeddings = embeddingStats && embeddingStats.total_embeddings > 0;
  const isModelLoading = embeddingStats && !embeddingStats.model_ready;
  const modelStatus = embeddingStats?.model_status || "loading";

  return (
    <Card className={cn("w-full", className)}>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-lg">
          <Sparkles className="h-5 w-5 text-yellow-500" />
          {t("title")}
          {isModelLoading && (
            <Badge variant="outline" className="ml-2 text-xs font-normal">
              <Loader2 className="mr-1 h-3 w-3 animate-spin" />
              {t("modelLoading")}
            </Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Model loading notification */}
        {isModelLoading && (
          <div className="flex items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 p-3 text-blue-800">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span className="text-sm">
              {t("modelLoadingMessage")}
            </span>
          </div>
        )}

        {/* Warning if records need embeddings */}
        {!isModelLoading && hasRecordsWithoutEmbeddings && (
          <div className="flex items-center justify-between rounded-lg border border-yellow-200 bg-yellow-50 p-3">
            <div className="flex items-center gap-2 text-yellow-800">
              <AlertCircle className="h-4 w-4" />
              <span className="text-sm">
                {t("embeddingsNeeded", { count: embeddingStats.records_without_embeddings })}
              </span>
            </div>
            <Button
              size="sm"
              variant="outline"
              onClick={() => generateMutation.mutate()}
              disabled={generateMutation.isPending}
            >
              {generateMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="mr-2 h-4 w-4" />
              )}
              {t("generateEmbeddings")}
            </Button>
          </div>
        )}

        {/* Search Input */}
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              ref={searchInputRef}
              placeholder={`${t("placeholder")} (Ctrl+K)`}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              className="pl-9 pr-9"
            />
            {query && (
              <Button
                variant="ghost"
                size="icon"
                className="absolute right-1 top-1/2 h-7 w-7 -translate-y-1/2"
                onClick={handleClear}
              >
                <X className="h-4 w-4" />
              </Button>
            )}
          </div>
          <Button
            onClick={handleSearch}
            disabled={!query.trim() || searchMutation.isPending || isModelLoading}
            title={isModelLoading ? t("modelLoadingMessage") : undefined}
          >
            {searchMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              t("searchButton")
            )}
          </Button>
        </div>

        {/* Filters */}
        <div className="flex gap-2">
          <Select value={recordType} onValueChange={setRecordType}>
            <SelectTrigger className="w-[140px]">
              <SelectValue placeholder={t("typeFilter")} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t("allTypes")}</SelectItem>
              <SelectItem value="FORM">{tType("form")}</SelectItem>
              <SelectItem value="EMAIL">{tType("email")}</SelectItem>
              <SelectItem value="INVOICE">{tType("invoice")}</SelectItem>
            </SelectContent>
          </Select>

          <Select value={status} onValueChange={setStatus}>
            <SelectTrigger className="w-[140px]">
              <SelectValue placeholder={t("statusFilter")} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t("allStatuses")}</SelectItem>
              <SelectItem value="pending">{tStatus("pending")}</SelectItem>
              <SelectItem value="approved">{tStatus("approved")}</SelectItem>
              <SelectItem value="rejected">{tStatus("rejected")}</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Results */}
        {isExpanded && (
          <>
            <Separator />
            <div className="space-y-2">
              {searchMutation.isPending && (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
              )}

              {!searchMutation.isPending && displayResults && displayResults.results.length === 0 && (
                <div className="py-8 text-center text-muted-foreground">
                  {t("noResults", { query: displayResults.query })}
                </div>
              )}

              {!searchMutation.isPending && displayResults && displayResults.results.length > 0 && (
                <>
                  <div className="flex items-center justify-between text-sm text-muted-foreground">
                    <span>
                      {t("foundResults", { count: displayResults.total })}
                    </span>
                    <span className="text-xs">
                      {t("aiModel")}: {displayResults.model}
                    </span>
                  </div>

                  <ScrollArea className="h-[300px]">
                    <div className="space-y-2">
                      {displayResults.results.map((result: SearchResult) => (
                        <SearchResultCard
                          key={result.record.id}
                          result={result}
                          getRecordIcon={getRecordIcon}
                          formatSimilarity={formatSimilarity}
                          onClick={onResultClick}
                        />
                      ))}
                    </div>
                  </ScrollArea>
                </>
              )}

              {searchMutation.isError && (
                <div className="py-4 text-center text-destructive">
                  {t("searchFailed")}
                </div>
              )}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

interface SearchResultCardProps {
  result: SearchResult;
  getRecordIcon: (type: string) => React.ReactNode;
  formatSimilarity: (score: number) => string;
  onClick?: (recordId: string) => void;
}

function SearchResultCard({
  result,
  getRecordIcon,
  formatSimilarity,
  onClick,
}: SearchResultCardProps) {
  const record = result.record;
  const extraction = record.extraction;

  const getTitle = () => {
    if (extraction.form_data?.full_name) return extraction.form_data.full_name;
    if (extraction.email_data?.sender_name) return extraction.email_data.sender_name;
    if (extraction.invoice_data?.client_name) return extraction.invoice_data.client_name;
    return extraction.source_file;
  };

  const getSubtitle = () => {
    if (extraction.form_data?.service_interest) return extraction.form_data.service_interest;
    if (extraction.email_data?.subject) return extraction.email_data.subject;
    if (extraction.invoice_data?.invoice_number) return extraction.invoice_data.invoice_number;
    return extraction.record_type;
  };

  return (
    <Link href={`/records/${record.id}`}>
      <div
        className="flex items-center gap-3 rounded-lg border p-3 transition-colors hover:bg-muted/50 cursor-pointer"
        onClick={(e) => {
          // Mark that we're navigating to a record from search
          // This allows state restoration when coming back
          if (typeof window !== "undefined") {
            sessionStorage.setItem(NAVIGATED_TO_RESULT_KEY, "true");
          }
          if (onClick) {
            e.preventDefault();
            onClick(record.id);
          }
        }}
      >
        {/* Icon */}
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted">
          {getRecordIcon(extraction.record_type)}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium truncate">{getTitle()}</span>
            <StatusBadge status={record.status} />
          </div>
          <p className="text-sm text-muted-foreground truncate">
            {getSubtitle()}
          </p>
          {result.highlight && (
            <p className="text-xs text-muted-foreground mt-1 line-clamp-1">
              {result.highlight}
            </p>
          )}
        </div>

        {/* Similarity Score */}
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="font-mono">
            {formatSimilarity(result.similarity)}
          </Badge>
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
        </div>
      </div>
    </Link>
  );
}
