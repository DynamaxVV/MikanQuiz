import { ref } from 'vue';
import type { FontOption } from '@/types';

type FontState = 'idle' | 'loading' | 'ready' | 'failed' | 'missing';
type FontStatus = { family: string; state: Exclude<FontState, 'idle' | 'missing'> };

const fontStates = ref(new Map<string, FontStatus>());
const fontFamilies = new Map<string, string>();
const fontError = ref('');
const API_BASE = import.meta.env.VITE_API_BASE ?? '/api/v1';

// Limit concurrent font downloads in browser to prevent request congestion
const MAX_CONCURRENT_LOADS = 4;
let activeLoads = 0;
const queue: (() => void)[] = [];

function pumpQueue(): void {
  while (activeLoads < MAX_CONCURRENT_LOADS && queue.length > 0) {
    const next = queue.shift();
    if (next) {
      activeLoads++;
      next();
    }
  }
}

function setFontState(cacheKey: string, state: FontStatus): void {
  const next = new Map(fontStates.value);
  next.set(cacheKey, state);
  fontStates.value = next;
}

function familyFor(url: string, text?: string): string {
  const cacheKey = text ? `${url}::${text}` : url;
  const existing = fontFamilies.get(cacheKey);
  if (existing) return existing;
  const family = `fp-${fontFamilies.size + 1}`;
  fontFamilies.set(cacheKey, family);
  return family;
}

async function doLoadFont(option: Pick<FontOption, 'fontUrl' | 'name'>, cacheKey: string, family: string): Promise<void> {
  const text = option.name?.trim() || '';
  try {
    let proxyUrl = `${API_BASE}/fonts/stream?url=${encodeURIComponent(option.fontUrl!)}`;
    if (text) {
      proxyUrl += `&text=${encodeURIComponent(text)}`;
    }
    const face = new FontFace(family, `url("${proxyUrl}")`);
    await face.load();
    document.fonts.add(face);
    setFontState(cacheKey, { family, state: 'ready' });
    fontError.value = '';
  } catch {
    setFontState(cacheKey, { family, state: 'failed' });
  } finally {
    activeLoads--;
    pumpQueue();
  }
}

function enqueueFontLoad(option: Pick<FontOption, 'fontUrl' | 'name'>): void {
  if (!option.fontUrl) return;
  const text = option.name?.trim() || '';
  const cacheKey = text ? `${option.fontUrl}::${text}` : option.fontUrl;

  const current = fontStates.value.get(cacheKey);
  if (current?.state === 'loading' || current?.state === 'ready') return;

  const family = familyFor(option.fontUrl, text);
  setFontState(cacheKey, { family, state: 'loading' });

  queue.push(() => {
    void doLoadFont(option, cacheKey, family);
  });
  pumpQueue();
}

export function useFontRendering() {
  function fontStyle(option: Pick<FontOption, 'fontUrl' | 'name'>): Record<string, string> {
    if (!option.fontUrl) return {};
    const text = option.name?.trim() || '';
    const cacheKey = text ? `${option.fontUrl}::${text}` : option.fontUrl;
    const status = fontStates.value.get(cacheKey);
    if (!status) enqueueFontLoad(option);
    return status?.state === 'ready' ? { fontFamily: `'${status.family}', sans-serif` } : {};
  }

  function preloadFonts(options: Pick<FontOption, 'fontUrl' | 'name'>[]): void {
    options.forEach((option) => { enqueueFontLoad(option); });
  }

  function fontState(option: Pick<FontOption, 'fontUrl' | 'name'>): FontState {
    if (!option.fontUrl) return 'missing';
    const text = option.name?.trim() || '';
    const cacheKey = text ? `${option.fontUrl}::${text}` : option.fontUrl;
    return fontStates.value.get(cacheKey)?.state ?? 'idle';
  }

  return { fontError, fontState, fontStyle, preloadFonts };
}
