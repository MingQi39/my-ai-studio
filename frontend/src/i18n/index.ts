/**
 * i18n setup with IP-based language detection.
 *
 * Detection priority (when the user has not picked a language in the switcher):
 *   1. Persisted choice in localStorage (`app_lang`)
 *   2. IP geolocation (ipapi.co) → country / languages header
 *   3. `navigator.language` (only if IP lookup fails)
 *   4. Fallback: `en`
 */
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

import en from './locales/en.json';
import zhCN from './locales/zh-CN.json';
import zhTW from './locales/zh-TW.json';
import ja from './locales/ja.json';
import ko from './locales/ko.json';
import es from './locales/es.json';
import fr from './locales/fr.json';
import de from './locales/de.json';
import ru from './locales/ru.json';

export const SUPPORTED_LANGS = [
  { code: 'zh-CN', label: '简体中文' },
  { code: 'zh-TW', label: '繁體中文' },
  { code: 'en', label: 'English' },
  { code: 'ja', label: '日本語' },
  { code: 'ko', label: '한국어' },
  { code: 'es', label: 'Español' },
  { code: 'fr', label: 'Français' },
  { code: 'de', label: 'Deutsch' },
  { code: 'ru', label: 'Русский' },
] as const;

export type SupportedLang = typeof SUPPORTED_LANGS[number]['code'];

const SUPPORTED_CODES = SUPPORTED_LANGS.map((l) => l.code) as SupportedLang[];
const STORAGE_KEY = 'app_lang';
const FALLBACK: SupportedLang = 'en';
const IP_LOOKUP_TIMEOUT_MS = 4000;

/** Map a BCP-47-ish tag to one of our supported locales. */
function normalizeTag(tag: string | null | undefined): SupportedLang | null {
  if (!tag) return null;
  const lower = tag.toLowerCase().replace('_', '-');
  for (const code of SUPPORTED_CODES) {
    if (code.toLowerCase() === lower) return code;
  }
  if (lower.startsWith('zh')) {
    if (/(tw|hk|mo|hant)/.test(lower)) return 'zh-TW';
    return 'zh-CN';
  }
  const primary = lower.split('-')[0];
  for (const code of SUPPORTED_CODES) {
    if (code.toLowerCase() === primary) return code;
  }
  return null;
}

/** Country → locale map for IP-based detection. */
const COUNTRY_TO_LANG: Record<string, SupportedLang> = {
  CN: 'zh-CN',
  SG: 'zh-CN',
  MY: 'zh-CN',
  TW: 'zh-TW',
  HK: 'zh-TW',
  MO: 'zh-TW',
  JP: 'ja',
  KR: 'ko',
  US: 'en',
  GB: 'en',
  AU: 'en',
  CA: 'en',
  NZ: 'en',
  IE: 'en',
  IN: 'en',
  PH: 'en',
  ES: 'es',
  MX: 'es',
  AR: 'es',
  CO: 'es',
  CL: 'es',
  PE: 'es',
  VE: 'es',
  EC: 'es',
  FR: 'fr',
  BE: 'fr',
  LU: 'fr',
  MC: 'fr',
  DE: 'de',
  AT: 'de',
  CH: 'de',
  LI: 'de',
  RU: 'ru',
  BY: 'ru',
  KZ: 'ru',
  UA: 'ru',
};

function getStoredLanguage(): SupportedLang | null {
  try {
    return normalizeTag(window.localStorage.getItem(STORAGE_KEY));
  } catch {
    return null;
  }
}

function detectFromNavigator(): SupportedLang | null {
  if (typeof navigator === 'undefined') return null;
  const langs =
    navigator.languages && navigator.languages.length ? navigator.languages : [navigator.language];
  for (const tag of langs) {
    const m = normalizeTag(tag);
    if (m) return m;
  }
  return null;
}

async function detectByIp(signal: AbortSignal): Promise<SupportedLang | null> {
  try {
    const res = await fetch('https://ipapi.co/json/', { signal });
    if (!res.ok) return null;
    const data = (await res.json()) as { country_code?: string; languages?: string };
    const country = data.country_code?.toUpperCase();
    if (country && COUNTRY_TO_LANG[country]) {
      return COUNTRY_TO_LANG[country];
    }
    if (data.languages) {
      for (const tag of data.languages.split(',')) {
        const m = normalizeTag(tag.trim());
        if (m) return m;
      }
    }
    return null;
  } catch {
    return null;
  }
}

/** Sync init: only honor an explicit saved choice; otherwise start at fallback until IP resolves. */
function detectInitial(): SupportedLang {
  return getStoredLanguage() ?? FALLBACK;
}

function applyLanguageIfNeeded(lang: SupportedLang): void {
  if (lang !== i18n.language) {
    i18n.changeLanguage(lang).catch(() => {});
  }
}

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    'zh-CN': { translation: zhCN },
    'zh-TW': { translation: zhTW },
    ja: { translation: ja },
    ko: { translation: ko },
    es: { translation: es },
    fr: { translation: fr },
    de: { translation: de },
    ru: { translation: ru },
  },
  lng: detectInitial(),
  fallbackLng: FALLBACK,
  supportedLngs: SUPPORTED_CODES,
  interpolation: { escapeValue: false },
  returnNull: false,
});

/**
 * Resolve language from IP when the user has not saved a preference.
 * Browser locale is used only if the IP request fails or times out.
 */
export function refineByIp(): void {
  if (getStoredLanguage()) return;

  const ctrl = new AbortController();
  const timeout = window.setTimeout(() => ctrl.abort(), IP_LOOKUP_TIMEOUT_MS);

  detectByIp(ctrl.signal)
    .then((lang) => {
      if (getStoredLanguage()) return;
      const resolved = lang ?? detectFromNavigator() ?? FALLBACK;
      applyLanguageIfNeeded(resolved);
    })
    .finally(() => window.clearTimeout(timeout));
}

/** Persist the user's explicit language choice (disables IP auto-detection on next visits). */
export function setLanguage(code: SupportedLang): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, code);
  } catch {
    /* ignore */
  }
  i18n.changeLanguage(code).catch(() => {});
}

/** Clear saved preference so the next load uses IP detection again. */
export function clearStoredLanguage(): void {
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

/** Keep `<html lang>` in sync with the active locale. */
export function bindDocumentLanguage(): void {
  const apply = (lng: string) => {
    document.documentElement.lang = lng;
  };
  apply(i18n.language);
  i18n.on('languageChanged', apply);
}

export default i18n;
