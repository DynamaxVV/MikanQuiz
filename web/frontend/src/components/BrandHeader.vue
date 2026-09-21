<script setup lang="ts">
import { nextTick, ref, watch } from 'vue';
import { RouterLink, useRouter } from 'vue-router';
import { api } from '@/api/client';
import FeedbackDialog from '@/components/FeedbackDialog.vue';
import type { FeedbackContext } from '@/types';

withDefaults(defineProps<{ showBrand?: boolean; showFeedback?: boolean; feedbackSource?: string; feedbackContext?: FeedbackContext }>(), { showBrand: true, showFeedback: false, feedbackSource: 'unknown' });

const router = useRouter();
const displayName = ref(localStorage.getItem('hanzipen-display-name') ?? '');
const editing = ref(false);
const draftName = ref(displayName.value);
const dialog = ref<HTMLDialogElement>();

function openNameEditor(): void {
  draftName.value = displayName.value;
  editing.value = true;
}

function saveName(): void {
  displayName.value = draftName.value.trim().slice(0, 20);
  localStorage.setItem('hanzipen-display-name', displayName.value);
  editing.value = false;
}

async function goToAdmin(): Promise<void> {
  try { await api.getAdminSession(); await router.push('/admin/questions'); }
  catch { await router.push('/admin/login'); }
}

watch(editing, async (open) => {
  if (open) {
    await nextTick();
    dialog.value?.showModal();
  } else if (dialog.value?.open) {
    dialog.value.close();
  }
});

</script>

<template>
  <header class="brand-header">
    <RouterLink v-if="showBrand" class="brand" to="/" aria-label="返回砂糖橘的秘密小课堂首页">
      <span>砂糖橘的秘密小课堂</span>
    </RouterLink>
    <div class="header-actions">
      <button class="name-button" type="button" @click="openNameEditor">
        {{ displayName || '设置昵称' }}
      </button>
      <FeedbackDialog v-if="showFeedback" :source="feedbackSource" :context="feedbackContext" />
      <button class="admin-button" type="button" @click="goToAdmin">管理员登录</button>
    </div>
  </header>

  <dialog ref="dialog" class="name-dialog" aria-labelledby="name-dialog-title" @close="editing = false" @cancel.prevent="editing = false">
    <form method="dialog" @submit.prevent="saveName">
      <h2 id="name-dialog-title">设置你的昵称</h2>
      <p>提交记录会使用这个昵称，可随时修改。</p>
      <label>
        昵称
        <input v-model="draftName" maxlength="20" autofocus placeholder="例如：小砂糖" />
      </label>
      <div class="dialog-actions">
        <button type="button" class="quiet" @click="editing = false">取消</button>
        <button type="submit" class="primary">保存昵称</button>
      </div>
    </form>
  </dialog>
</template>

<style scoped>
.brand-header { display: flex; min-height: 72px; align-items: center; justify-content: space-between; gap: 16px; }
.brand { display: inline-flex; align-items: center; gap: 9px; font-size: 15px; font-weight: 750; color: var(--color-accent); }
.header-actions { display: flex; align-items: center; gap: 8px; margin-left: auto; }
.name-button, .admin-button, .quiet, .primary { border: 0; border-radius: var(--radius-button); min-height: 40px; padding: 0 14px; font-weight: 650; }
.name-button, .admin-button, .quiet { color: var(--color-text-muted); background: transparent; }
.name-button:hover, .admin-button:hover, .quiet:hover { color: var(--color-action); background: var(--color-surface-accent); }
.primary { color: #fff; background: var(--color-action); }
.primary:hover { background: var(--color-action-hover); }
.name-dialog { width: min(420px, calc(100vw - 32px)); padding: 0; border: 1px solid var(--color-border); border-radius: 20px; box-shadow: 0 20px 60px rgba(51, 39, 24, .23); }
.name-dialog::backdrop { background: rgba(51, 39, 24, .36); }
.name-dialog form { padding: 24px; }
.name-dialog h2 { margin: 0; font-size: 22px; }
.name-dialog p { margin: 8px 0 20px; color: var(--color-text-muted); line-height: 1.55; }
.name-dialog label { display: grid; gap: 7px; font-size: 14px; font-weight: 650; }
.name-dialog input { width: 100%; border: 1px solid var(--color-border); border-radius: var(--radius-input); padding: 11px 12px; color: var(--color-text); background: var(--color-surface-warm); }
.dialog-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 24px; }
@media (max-width: 600px) { .brand-header { min-height: 64px; } }
</style>
