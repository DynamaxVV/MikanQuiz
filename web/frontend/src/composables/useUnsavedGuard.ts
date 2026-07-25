import { ref, watch } from 'vue';
import { onBeforeRouteLeave } from 'vue-router';
import { ElMessageBox } from 'element-plus';

function stableStringify(value: unknown): string {
  if (value === null || value === undefined || typeof value !== 'object') return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(',')}]`;
  const keys = Object.keys(value as Record<string, unknown>).sort();
  return `{${keys.map((k) => `${JSON.stringify(k)}:${stableStringify((value as Record<string, unknown>)[k])}`).join(',')}}`;
}

export function useUnsavedGuard(getFormSnapshot: () => unknown) {
  const dirty = ref(false);
  let baseline = stableStringify(getFormSnapshot());

  watch(getFormSnapshot, (current) => {
    dirty.value = stableStringify(current) !== baseline;
  }, { deep: true });

  function markSaved(): void {
    baseline = stableStringify(getFormSnapshot());
    dirty.value = false;
  }

  onBeforeRouteLeave(async (_to, _from, next) => {
    if (!dirty.value) { next(); return; }
    try {
      await ElMessageBox.confirm('表单已修改但未保存，是否直接离开？', '未保存的更改', {
        confirmButtonText: '直接离开',
        cancelButtonText: '留在当前页',
        type: 'warning',
      });
      next();
    } catch {
      next(false);
    }
  });

  return { dirty, markSaved };
}
