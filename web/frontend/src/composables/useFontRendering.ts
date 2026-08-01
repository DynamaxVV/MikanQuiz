import { ref } from 'vue';
import type { FontOption } from '@/types';

type FontState = 'idle' | 'loading' | 'ready' | 'failed' | 'missing';
type FontStatus = { family: string; state: Exclude<FontState, 'idle' | 'missing'> };

const fontStates = ref(new Map<string, FontStatus>());
const fontFamilies = new Map<string, string>();
const fontError = ref('');
const API_BASE = import.meta.env.VITE_API_BASE ?? '/api/v1';

function setFontState(url: string, state: FontStatus): void {
  const next = new Map(fontStates.value);
  next.set(url, state);
  fontStates.value = next;
}

function familyFor(url: string): string {
  const existing = fontFamilies.get(url);
  if (existing) return existing;
  const family = `fp-${fontFamilies.size + 1}`;
  fontFamilies.set(url, family);
  return family;
}

async function loadFont(option: Pick<FontOption, 'fontUrl'>): Promise<void> {
  if (!option.fontUrl) return;
  const current = fontStates.value.get(option.fontUrl);
  if (current?.state === 'loading' || current?.state === 'ready') return;
  const family = familyFor(option.fontUrl);
  setFontState(option.fontUrl, { family, state: 'loading' });
  try {
    const proxyUrl = `${API_BASE}/fonts/stream?url=${encodeURIComponent(option.fontUrl)}`;
    const face = new FontFace(family, `url("${proxyUrl}")`);
    await face.load();
    document.fonts.add(face);
    setFontState(option.fontUrl, { family, state: 'ready' });
    fontError.value = '';
  } catch {
    setFontState(option.fontUrl, { family, state: 'failed' });
    fontError.value = '字体加载失败，已使用系统字体。';
  }
}

export function useFontRendering() {
  function fontStyle(option: Pick<FontOption, 'fontUrl'>): Record<string, string> {
    if (!option.fontUrl) return {};
    const status = fontStates.value.get(option.fontUrl);
    if (!status) void loadFont(option);
    return status?.state === 'ready' ? { fontFamily: `'${status.family}', sans-serif` } : {};
  }

  function preloadFonts(options: Pick<FontOption, 'fontUrl'>[]): void {
    options.forEach((option) => { void loadFont(option); });
  }

  function fontState(option: Pick<FontOption, 'fontUrl'>): FontState {
    if (!option.fontUrl) return 'missing';
    return fontStates.value.get(option.fontUrl)?.state ?? 'idle';
  }

  return { fontError, fontState, fontStyle, preloadFonts };
}
