import { onBeforeUnmount, ref } from 'vue';
import { api } from '@/api/client';

/** Share the global reusable explanation draft through the server; batch-local storage is layered by the caller. */
export function useFontExplanationCache() {
  const suggestion = ref('');
  let requestVersion = 0;
  let saveTimer: ReturnType<typeof setTimeout> | undefined;
  let pendingSave: { fontOptionId: string; explanation: string } | undefined;

  function flush(): void {
    clearTimeout(saveTimer);
    saveTimer = undefined;
    const pending = pendingSave;
    pendingSave = undefined;
    if (pending) void api.saveFontExplanationCache(pending.fontOptionId, pending.explanation).catch(() => undefined);
  }

  async function load(fontOptionId: string, getExplanation: () => string): Promise<void> {
    const version = ++requestVersion;
    flush();
    suggestion.value = '';
    if (!fontOptionId || getExplanation().trim()) return;
    try {
      const explanation = await api.getFontExplanationCache(fontOptionId);
      if (version === requestVersion && !getExplanation().trim()) suggestion.value = explanation;
    } catch {
      // Keep the editor usable while an older server is being upgraded.
    }
  }

  function input(fontOptionId: string, explanation: string): void {
    if (explanation.trim()) suggestion.value = '';
    if (pendingSave && pendingSave.fontOptionId !== fontOptionId) flush();
    clearTimeout(saveTimer);
    pendingSave = fontOptionId && explanation.trim() ? { fontOptionId, explanation: explanation.trim() } : undefined;
    if (!pendingSave) return;
    saveTimer = setTimeout(flush, 500);
  }

  function reset(): void {
    requestVersion++;
    flush();
    suggestion.value = '';
  }

  onBeforeUnmount(reset);
  return { suggestion, load, input, flush, reset };
}
