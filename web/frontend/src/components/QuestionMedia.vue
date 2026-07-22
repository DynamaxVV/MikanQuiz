<script setup lang="ts">
import { ref } from 'vue';
import ImageLightbox from './ImageLightbox.vue';

defineProps<{ imageUrl: string | null; text: string }>();
const failed = ref(false);
const expanded = ref(false);
function retry(): void { failed.value = false; }
</script>

<template>
  <div v-if="imageUrl" class="media">
    <button type="button" class="image-button" :aria-label="`${text}的题目图片，点击查看原图`" @click="expanded = true">
      <span v-if="!failed" class="image-frame" :style="{ backgroundImage: `url(&quot;${imageUrl}&quot;)` }"><img class="image-probe" :src="imageUrl" alt="" @error="failed = true" /></span>
      <span v-else class="image-error">图片加载失败，请检查图片 URL 或重试。</span>
    </button>
    <div class="media-footer">
      <span v-if="!failed">点击查看原图</span>
      <button v-else type="button" @click="retry">重试图片</button>
    </div>
    <ImageLightbox :open="expanded" :src="imageUrl" :alt="`${text}的题目图片`" @close="expanded = false" />
  </div>
  <div v-else class="no-image">本题没有配图</div>
</template>

<style scoped>
.media { overflow: hidden; border: 1px solid var(--color-border); border-radius: 20px; background: var(--color-surface-warm); }
.image-button { display: grid; width: 100%; height: min(42vh, 360px); padding: 16px; place-items: center; border: 0; background: transparent; box-sizing: border-box; }
.image-frame { display: block; width: 100%; height: 100%; background-position: center; background-repeat: no-repeat; background-size: contain; }
.image-probe { position: absolute; width: 1px; height: 1px; opacity: 0; pointer-events: none; }
.media-footer { display: flex; min-height: 42px; align-items: center; justify-content: center; gap: 10px; color: var(--color-text-muted); font-size: 13px; background: rgba(255, 255, 255, .66); }
.media-footer button { border: 0; color: var(--color-action); background: transparent; font-weight: 650; }
.image-error { max-width: 280px; color: var(--color-danger); line-height: 1.6; text-align: center; }
.no-image { display: grid; min-height: 200px; place-items: center; border: 1px dashed var(--color-border); border-radius: 20px; color: var(--color-text-muted); background: var(--color-surface-warm); }
</style>
