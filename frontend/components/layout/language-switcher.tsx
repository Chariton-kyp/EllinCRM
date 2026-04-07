"use client";

import { useState } from "react";
import { useLocale } from "next-intl";
import { Globe, Loader2 } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const languages = [
  { code: "en", name: "English", flag: "🇬🇧" },
  { code: "el", name: "Ελληνικά", flag: "🇬🇷" },
] as const;

export function LanguageSwitcher() {
  const currentLocale = useLocale();
  const [isChanging, setIsChanging] = useState(false);

  const handleLocaleChange = (newLocale: string) => {
    if (newLocale === currentLocale || isChanging) return;

    // Show loading state
    setIsChanging(true);

    // Set cookie that will be read by the server
    document.cookie = `NEXT_LOCALE=${newLocale};path=/;max-age=31536000;SameSite=Lax`;

    // Use a small delay to show the loading state, then reload
    // This is the only reliable way to ensure the cookie is read by the server
    setTimeout(() => {
      window.location.reload();
    }, 100);
  };

  const currentLanguage = languages.find((lang) => lang.code === currentLocale);

  return (
    <Select
      value={currentLocale}
      onValueChange={handleLocaleChange}
      disabled={isChanging}
    >
      <SelectTrigger className="w-auto gap-2 border-none bg-transparent shadow-none focus:ring-0">
        {isChanging ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Globe className="h-4 w-4" />
        )}
        <SelectValue>
          <span className="hidden sm:inline">
            {currentLanguage?.flag} {currentLanguage?.code.toUpperCase()}
          </span>
          <span className="sm:hidden">{currentLanguage?.flag}</span>
        </SelectValue>
      </SelectTrigger>
      <SelectContent>
        {languages.map((lang) => (
          <SelectItem key={lang.code} value={lang.code}>
            <span className="mr-2">{lang.flag}</span>
            {lang.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
