<script setup lang="ts">
import { nextTick, ref, watch } from 'vue';

const props = defineProps<{ open: boolean; src: string; alt: string }>();
const emit = defineEmits<{ close: [] }>();
const dialog = ref<HTMLDialogElement>();
const trigger = ref<HTMLElement | null>(null);
const zoom = ref(1);

function close(): void { emit('close'); }
function adjustZoom(delta: number): void {
  zoom.value = Math.min(3, Math.max(0.5, Math.round((zoom.value + delta) * 100) / 100));
}
function resetZoom(): void { zoom.value = 1; }

watch(() => props.open, async (open) => {
  if (open) {
    resetZoom();
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
    <div class="image-stage">
      <img :src="src" :alt="alt" :style="{ transform: `scale(${zoom})` }" />
    </div>
    <div class="zoom-controls" role="group" aria-label="调整图片大小">
      <button type="button" aria-label="缩小图片" :disabled="zoom <= 0.5" @click="adjustZoom(-0.25)">−</button>
      <button type="button" aria-label="恢复原图大小" @click="resetZoom">{{ Math.round(zoom * 100) }}%</button>
      <button type="button" aria-label="放大图片" :disabled="zoom >= 3" @click="adjustZoom(0.25)">＋</button>
    </div>
  </dialog>
</template>

<style scoped>
.lightbox { width: min(1200px, calc(100vw - 40px)); height: min(88vh, 880px); padding: 24px 24px 62px; border: 1px solid var(--color-border); border-radius: 22px; background: #fffdf9; box-shadow: 0 24px 80px rgba(51, 39, 24, .3); overflow: hidden; box-sizing: border-box; }
.lightbox::backdrop { background: rgba(51, 39, 24, .68); }
.image-stage { display: grid; width: 100%; height: 100%; place-items: center; overflow: auto; }
.image-stage img { display: block; width: 100%; height: 100%; object-fit: contain; transform-origin: center; transition: transform 160ms ease-out; }
.close { position: absolute; top: 10px; right: 12px; z-index: 1; display: grid; width: 40px; height: 40px; place-items: center; border: 1px solid var(--color-border); border-radius: 50%; color: var(--color-text); background: #fff; font-size: 28px; line-height: 1; }
.zoom-controls { position: absolute; right: 50%; bottom: 14px; z-index: 1; display: flex; gap: 4px; transform: translateX(50%); }
.zoom-controls button { min-width: 36px; min-height: 32px; border: 1px solid var(--color-border); border-radius: 8px; color: var(--color-text); background: #fff; font: inherit; cursor: pointer; }
.zoom-controls button:disabled { opacity: .45; cursor: default; }
</style>
