import type { FontOption } from '@/types';

const loadedFamilies = new Map<string, string>();
const pendingRules: string[] = [];
let styleElement: HTMLStyleElement | null = null;
const API_BASE = import.meta.env.VITE_API_BASE ?? '/api/v1';

function flushFontRules(): void {
  if (!pendingRules.length) return;
  if (!styleElement) {
    styleElement = document.createElement('style');
    document.head.appendChild(styleElement);
  }
  styleElement.textContent = pendingRules.join('\n');
}

export function useFontRendering() {
  function fontFamily(option: Pick<FontOption, 'fontUrl'>): string | undefined {
    if (!option.fontUrl) return undefined;
    let family = loadedFamilies.get(option.fontUrl);
    if (!family) {
      family = `fp-${crypto.randomUUID().slice(0, 8)}`;
      loadedFamilies.set(option.fontUrl, family);
      const proxyUrl = `${API_BASE}/fonts/stream?url=${encodeURIComponent(option.fontUrl)}`;
      pendingRules.push(`@font-face{font-family:'${family}';src:url('${proxyUrl}');font-weight:normal;font-style:normal;font-display:swap}`);
    }
    return family;
  }

  function fontStyle(option: Pick<FontOption, 'fontUrl'>): Record<string, string> {
    const family = fontFamily(option);
    if (family) flushFontRules();
    return family ? { fontFamily: `'${family}', sans-serif` } : {};
  }

  function preloadFonts(options: Pick<FontOption, 'fontUrl'>[]): void {
    for (const option of options) fontFamily(option);
    flushFontRules();
  }

  return { fontFamily, fontStyle, preloadFonts };
}
