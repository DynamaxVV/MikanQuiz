<script setup lang="ts">
import { nextTick, ref, watch } from 'vue';

const props = defineProps<{ open: boolean; src: string; alt: string }>();
const emit = defineEmits<{ close: [] }>();
const dialog = ref<HTMLDialogElement>();
const trigger = ref<HTMLElement | null>(null);

function close(): void { emit('close'); }

watch(() => props.open, async (open) => {
  if (open) {
    trigger.value = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    await nextTick();
    dialog.value?.showModal();
  } else if (dialog.value?.open) {
    dialog.value.close();
    trigger.value?.focus();
  }
});
</script>

<template>
  <dialog ref="dialog" class="lightbox" aria-label="图片查看器" @close="close" @cancel.prevent="close">
    <button class="close" type="button" aria-label="关闭原图查看器" @click="close">×</button>
    <img :src="src" :alt="alt" />
  </dialog>
</template>

<style scoped>
.lightbox { width: min(1200px, calc(100vw - 40px)); height: min(88vh, 880px); padding: 24px; border: 1px solid var(--color-border); border-radius: 22px; background: #fffdf9; box-shadow: 0 24px 80px rgba(51, 39, 24, .3); }
.lightbox::backdrop { background: rgba(51, 39, 24, .68); }
.lightbox img { display: block; width: 100%; height: 100%; object-fit: contain; }
.close { position: absolute; top: 10px; right: 12px; z-index: 1; display: grid; width: 40px; height: 40px; place-items: center; border: 1px solid var(--color-border); border-radius: 50%; color: var(--color-text); background: #fff; font-size: 28px; line-height: 1; }
</style>
