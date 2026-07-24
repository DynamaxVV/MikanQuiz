import type { FontOption } from '@/types';

const loadedFamilies = new Map<string, string>();
const API_BASE = import.meta.env.VITE_API_BASE ?? '/api/v1';

export function useFontRendering() {
  function fontFamily(option: Pick<FontOption, 'fontUrl'>): string | undefined {
    if (!option.fontUrl) return undefined;
    let family = loadedFamilies.get(option.fontUrl);
    if (!family) {
      family = `fp-${crypto.randomUUID().slice(0, 8)}`;
      loadedFamilies.set(option.fontUrl, family);
      const proxyUrl = `${API_BASE}/fonts/stream?url=${encodeURIComponent(option.fontUrl)}`;
      const style = document.createElement('style');
      style.textContent = `@font-face{font-family:'${family}';src:url('${proxyUrl}');font-weight:normal;font-style:normal;font-display:swap}`;
      document.head.appendChild(style);
    }
    return family;
  }

  function fontStyle(option: Pick<FontOption, 'fontUrl'>): Record<string, string> {
    const family = fontFamily(option);
    return family ? { fontFamily: `'${family}', sans-serif`, fontSize: '120%' } : {};
  }

  return { fontFamily, fontStyle };
}
