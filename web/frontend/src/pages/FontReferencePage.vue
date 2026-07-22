<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue';
import { api } from '@/api/client';
import BrandHeader from '@/components/BrandHeader.vue';
import ErrorPanel from '@/components/ErrorPanel.vue';
import type { FontReference } from '@/types';

const keyword = ref('');
const references = ref<FontReference[]>([]);
const selectedId = ref('');
const loading = ref(true);
const error = ref('');
const dialog = ref<HTMLDialogElement>();
const trigger = ref<HTMLElement | null>(null);
const filtered = computed(() => references.value.filter((item) =>
  item.title.toLocaleLowerCase().includes(keyword.value.trim().toLocaleLowerCase()),
));
const selected = computed<FontReference | null>(() =>
  filtered.value.find((item) => item.id === selectedId.value) ?? filtered.value[0] ?? null,
);

async function loadReferences(): Promise<void> {
  loading.value = true;
  error.value = '';
  try {
    references.value = await api.listFontReferences();
    selectedId.value = references.value[0]?.id ?? '';
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '字体对照图加载失败。';
  } finally {
    loading.value = false;
  }
}

function select(id: string): void { selectedId.value = id; }
async function openImage(): Promise<void> {
  trigger.value = document.activeElement as HTMLElement;
  await nextTick();
  dialog.value?.showModal();
}
function closeImage(): void { dialog.value?.close(); trigger.value?.focus(); }

onMounted(loadReferences);
</script>

<template>
  <main class="font-reference-page">
    <div class="content">
      <BrandHeader />
      <section aria-labelledby="font-reference-title">
        <h1 id="font-reference-title" class="page-title">字体对照表</h1>
        <p class="page-description">选择左侧条目查看原图与注释。</p>
        <p v-if="loading" class="loading-state">正在加载对照图…</p>
        <ErrorPanel v-else-if="error" :message="error" @retry="loadReferences" />
        <div v-else-if="references.length === 0" class="empty-state card">
          <strong>尚未配置字体对照图</strong><span>管理员可在后台上传第一张对照图。</span>
        </div>
        <div v-else class="reference-layout">
          <aside class="reference-list card">
            <label class="search-label">搜索标题<input v-model="keyword" type="search" placeholder="输入关键词" /></label>
            <div v-if="filtered.length" class="reference-items">
              <button v-for="item in filtered" :key="item.id" type="button" :class="{ selected: selected?.id === item.id }" @click="select(item.id)">
                <img :src="item.imageUrl" alt="" /><span>{{ item.title }}</span>
              </button>
            </div>
            <p v-else class="no-match">没有匹配的对照图。</p>
          </aside>
          <section v-if="selected" class="reference-view card">
            <h2>{{ selected.title }}</h2><p v-if="selected.note">{{ selected.note }}</p>
            <button class="image-trigger" type="button" @click="openImage"><img :src="selected.imageUrl" :alt="selected.title" /><span>点击查看原图</span></button>
          </section>
        </div>
      </section>
    </div>
  </main>
  <dialog ref="dialog" class="lightbox" aria-label="字体对照图查看器" @close="trigger?.focus()" @cancel.prevent="closeImage"><button type="button" aria-label="关闭原图查看器" @click="closeImage">×</button><img v-if="selected" :src="selected.imageUrl" :alt="selected.title" /></dialog>
</template>

<style scoped>
.font-reference-page { min-height: 100vh; background: var(--color-bg); }.content { width: min(1280px, calc(100% - clamp(48px, 8vw, 128px))); margin: 0 auto; }.page-description { max-width: 680px; }.loading-state { margin-top: 34px; color: var(--color-text-muted); }.empty-state { margin-top: 34px; gap: 10px; }.reference-layout { display: grid; grid-template-columns: 280px minmax(0, 1fr); gap: 24px; margin-top: 34px; }.reference-list { overflow: hidden; padding: 16px; }.search-label { display: grid; gap: 8px; color: var(--color-text-muted); font-size: 13px; font-weight: 700; }.search-label input { width: 100%; border: 1px solid var(--color-border); border-radius: 10px; padding: 10px; color: var(--color-text); background: var(--color-surface-warm); }.reference-items { display: grid; gap: 8px; margin-top: 16px; }.reference-items button { display: grid; grid-template-columns: 46px 1fr; align-items: center; gap: 10px; min-height: 56px; overflow: hidden; border: 1px solid transparent; border-radius: 12px; padding: 5px; color: var(--color-text); background: transparent; text-align: left; }.reference-items button:hover, .reference-items button.selected { border-color: #ebcfad; background: var(--color-surface-accent); }.reference-items button:focus-visible, .image-trigger:focus-visible { outline: 3px solid var(--color-action); outline-offset: 3px; }.reference-items img { width: 46px; height: 44px; object-fit: cover; border-radius: 8px; }.no-match { color: var(--color-text-muted); font-size: 14px; }.reference-view { min-height: 600px; padding: 28px; }.reference-view h2 { margin: 0; font-size: 24px; }.reference-view > p { color: var(--color-text-muted); line-height: 1.6; white-space: pre-wrap; }.image-trigger { display: grid; width: 100%; min-height: 450px; margin-top: 20px; place-items: center; overflow: hidden; border: 1px solid var(--color-border); border-radius: 18px; color: var(--color-text-muted); background: var(--color-surface-warm); }.image-trigger img { width: 100%; max-height: 560px; object-fit: contain; }.image-trigger span { padding: 10px; font-size: 13px; }.lightbox { width: min(1200px, calc(100vw - 40px)); height: min(88vh, 880px); padding: 24px; border: 1px solid var(--color-border); border-radius: 22px; background: #fffdf9; }.lightbox::backdrop { background: rgba(51, 39, 24, .68); }.lightbox button { position: absolute; top: 10px; right: 12px; display: grid; width: 40px; height: 40px; place-items: center; border: 1px solid var(--color-border); border-radius: 50%; background: #fff; font-size: 28px; }.lightbox img { width: 100%; height: 100%; object-fit: contain; }
@media (max-width: 767px) { .content { width: min(100% - 32px, 1280px); }.reference-layout { grid-template-columns: 1fr; }.reference-view { min-height: auto; }.image-trigger { min-height: 300px; } }
</style>
