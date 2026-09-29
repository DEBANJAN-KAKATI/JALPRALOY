// Tiny i18n: English, Assamese, Bengali, Hindi.
// Have native speakers review as/bn/hi before the demo.
import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import as from "./as.json";
import bn from "./bn.json";
import en from "./en.json";
import hi from "./hi.json";

export type Lang = "en" | "as" | "bn" | "hi";
type Dict = typeof en;

const DICTS: Record<Lang, Dict> = { en, as, bn, hi };
export const LANG_LABEL: Record<Lang, string> = { en: "EN", as: "অস", bn: "বাং", hi: "हि" };
// BCP-47 tags for speech synthesis; browser voice support for as-IN is limited.
export const SPEECH_LANG: Record<Lang, string> = { en: "en-IN", as: "as-IN", bn: "bn-IN", hi: "hi-IN" };

interface I18n {
  lang: Lang;
  setLang: (l: Lang) => void;
  /** t("brief_rain", { mm: 42 }) fills {mm} in the template */
  t: (key: string, vars?: Record<string, string | number>) => string;
}

const Ctx = createContext<I18n | null>(null);

function initialLang(): Lang {
  try {
    const saved = localStorage.getItem("lang") as Lang | null;
    if (saved && saved in DICTS) return saved;
  } catch {
    /* storage unavailable */
  }
  return "en";
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(initialLang);
  const value = useMemo<I18n>(
    () => ({
      lang,
      setLang: (l) => {
        setLangState(l);
        try {
          localStorage.setItem("lang", l);
        } catch {
          /* ignore */
        }
      },
      t: (key, vars) => {
        const template = (DICTS[lang] as Record<string, string>)[key] ?? (en as Record<string, string>)[key] ?? key;
        return vars ? template.replace(/\{(\w+)\}/g, (m, k: string) => (k in vars ? String(vars[k]) : m)) : template;
      },
    }),
    [lang],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useI18n(): I18n {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useI18n outside I18nProvider");
  return ctx;
}
