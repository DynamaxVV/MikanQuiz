import { ref, watch } from 'vue';
import { onBeforeRouteLeave } from 'vue-router';

function stableStringify(value: unknown): string {
  if (value === null || value === undefined || typeof value !== 'object') return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(',')}]`;
  const keys = Object.keys(value as Record<string, unknown>).sort();
  return `{${keys.map((k) => `${JSON.stringify(k)}:${stableStringify((value as Record<string, unknown>)[k])}`).join(',')}}`;
}

function showConfirmDialog(title: string, message: string, confirmText: string, cancelText: string): Promise<boolean> {
  return new Promise<boolean>((resolve) => {
    const style = document.createElement('style');
    style.textContent = `#unsaved-dialog{width:min(420px,calc(100vw - 32px));padding:0;border:1px solid #F3E5D3;border-radius:20px;background:#FFFDF9;box-shadow:0 20px 60px rgba(51,39,24,.23)}#unsaved-dialog::backdrop{background:rgba(51,39,24,.36)}#unsaved-dialog .ud-body{padding:24px}#unsaved-dialog h2{margin:0;font-size:22px;color:#332718}#unsaved-dialog p{margin:8px 0 0;color:#816E59;font-size:15px;line-height:1.55}#unsaved-dialog .ud-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:24px}#unsaved-dialog button{border:0;border-radius:14px;min-height:40px;padding:0 16px;font-size:14px;font-weight:650;cursor:pointer;transition:background 120ms}#unsaved-dialog .ud-cancel{color:#816E59;background:transparent}#unsaved-dialog .ud-cancel:hover{color:#A94F1F;background:#FFF0D8}#unsaved-dialog .ud-confirm{color:#fff;background:#A94F1F}#unsaved-dialog .ud-confirm:hover{background:#913F16}@keyframes ud-in{from{opacity:0;transform:scale(.98)}to{opacity:1;transform:scale(1)}}@keyframes ud-out{from{opacity:1;transform:scale(1)}to{opacity:0;transform:scale(.98)}}`;
    document.head.appendChild(style);

    const dialog = document.createElement('dialog');
    dialog.id = 'unsaved-dialog';
    dialog.style.animation = 'ud-in 180ms ease-out';
    dialog.innerHTML = `<div class="ud-body"><h2>${title}</h2><p>${message}</p><div class="ud-actions"><button type="button" class="ud-cancel">${cancelText}</button><button type="button" class="ud-confirm">${confirmText}</button></div></div>`;
    document.body.appendChild(dialog);

    let settled = false;
    function finish(): void {
      if (settled) return;
      settled = true;
      dialog.style.animation = 'ud-out 140ms ease-in';
      setTimeout(() => { dialog.close(); }, 130);
    }
    dialog.addEventListener('close', () => {
      resolve(settled ? (dialog.returnValue === 'confirm') : false);
      dialog.remove();
      style.remove();
    });
    dialog.querySelector('.ud-cancel')!.addEventListener('click', () => finish(), { once: true });
    dialog.querySelector('.ud-confirm')!.addEventListener('click', () => { dialog.returnValue = 'confirm'; finish(); }, { once: true });

    dialog.showModal();
  });
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
    const confirmed = await showConfirmDialog(
      '未保存的更改',
      '表单已修改但未保存，是否直接离开？',
      '直接离开',
      '留在当前页',
    );
    next(confirmed);
  });

  return { dirty, markSaved };
}
