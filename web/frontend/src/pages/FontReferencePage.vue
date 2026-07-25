<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue';
import { api } from '@/api/client';
import BrandHeader from '@/components/BrandHeader.vue';
import ErrorPanel from '@/components/ErrorPanel.vue';
import type { FontReference } from '@/types';

const keyword = ref('');
const references = ref<FontReference[]>([]);
const loading = ref(true);
const error = ref('');
const starFilter = ref(0);
const selected = ref<FontReference | null>(null);

const filtered = computed(() =>
  references.value.filter((item) => {
    if (starFilter.value && item.difficulty !== starFilter.value) return false;
    if (keyword.value.trim() && !item.title.toLowerCase().includes(keyword.value.trim().toLowerCase())) return false;
    return true;
  }),
);

function stars(difficulty: number): string {
  return '★'.repeat(difficulty) + '☆'.repeat(3 - difficulty);
}
function toggleStar(level: number): void {
  starFilter.value = starFilter.value === level ? 0 : level;
}
function openCard(card: FontReference): void { selected.value = card; }
function closeCard(): void { selected.value = null; }

watch(selected, (value) => {
  document.body.style.overflow = value ? 'hidden' : '';
});

onBeforeUnmount(() => { document.body.style.overflow = ''; });

async function loadReferences(): Promise<void> {
  loading.value = true;
  error.value = '';
  try { references.value = await api.listFontReferences(); }
  catch (caught) { error.value = caught instanceof Error ? caught.message : '嵌字笔记加载失败。'; }
  finally { loading.value = false; }
}

onMounted(loadReferences);
</script>

<template>
  <main class="font-reference-page">
    <div class="content">
      <BrandHeader />
      <section aria-labelledby="font-reference-title">
        <h1 id="font-reference-title" class="page-title">嵌字小本本</h1>
        <p class="page-description">一点点点点也许嵌字会用上的教程</p>

        <p v-if="loading" class="loading-state">正在加载…</p>
        <ErrorPanel v-else-if="error" :message="error" @retry="loadReferences" />

        <template v-else>
          <div class="filter-bar">
            <label class="search-label">搜索卡片标题
              <input v-model="keyword" type="search" placeholder="输入关键词" />
            </label>
            <div class="star-filter" aria-label="按难度筛选">
              <button v-for="star in 3" :key="star" type="button" :class="{ active: starFilter === 0 || starFilter === star }" :aria-pressed="starFilter === 0 || starFilter === star" @click="toggleStar(star)">{{ '★'.repeat(star) }}</button>
            </div>
          </div>

          <div v-if="references.length === 0" class="empty-state card">
            <strong>尚未配置嵌字笔记卡片</strong><span>管理员可在后台上传第一张卡片。</span>
          </div>
          <div v-else-if="filtered.length === 0" class="empty-state card">
            <strong>没有匹配的卡片</strong>
          </div>

          <div v-else class="card-grid">
            <div v-for="card in filtered" :key="card.id" class="tutorial-card" tabindex="0" @click="openCard(card)" @keydown.enter="openCard(card)">
              <div class="card-head">
                <h2>{{ card.title }}</h2>
                <span class="card-stars" aria-label="难度 {{ card.difficulty }} 星">{{ stars(card.difficulty) }}</span>
              </div>
              <div class="card-body">
                <img :src="card.imageUrl" :alt="card.title" />
                <p>{{ card.note || '暂无说明' }}</p>
              </div>
            </div>
          </div>
        </template>
      </section>
    </div>
  </main>

  <Teleport to="body">
    <Transition name="lightbox">
      <div v-if="selected" class="lightbox-overlay" @click="closeCard">
        <div class="lightbox-card" @click.stop>
          <div class="card-head">
            <h2>{{ selected.title }}</h2>
            <span class="card-stars" aria-label="难度 {{ selected.difficulty }} 星">{{ stars(selected.difficulty) }}</span>
          </div>
          <div class="card-body">
            <img :src="selected.imageUrl" :alt="selected.title" />
            <p>{{ selected.note || '暂无说明' }}</p>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.font-reference-page { min-height: 100vh; background: var(--color-bg); }
.content { width: min(1280px, calc(100% - clamp(48px, 8vw, 128px))); margin: 0 auto; padding-bottom: 64px; }
.page-description { max-width: 680px; color: var(--color-text-muted); font-size: 15px; line-height: 1.6; }
.loading-state { margin-top: 34px; color: var(--color-text-muted); }
.empty-state { margin-top: 34px; gap: 10px; text-align: center; padding: 48px 24px; }

.filter-bar { display: flex; flex-wrap: wrap; gap: 20px; align-items: flex-end; margin-top: 28px; }
.search-label { display: grid; gap: 8px; color: var(--color-text-muted); font-size: 13px; font-weight: 700; }
.search-label input { width: 260px; border: 1px solid var(--color-border); border-radius: 10px; padding: 10px 14px; color: var(--color-text); background: var(--color-surface-warm); }
.star-filter { display: flex; gap: 8px; }
.star-filter button { min-height: 34px; border: 1px solid var(--color-border); border-radius: 999px; padding: 0 12px; color: #b9aa99; background: var(--color-surface-warm); font-size: 14px; letter-spacing: 1px; cursor: pointer; }
.star-filter button.active { border-color: #ebcfad; color: var(--color-action); background: var(--color-surface-accent); }

.card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 20px; margin-top: 28px; }
.tutorial-card { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 18px; box-shadow: var(--shadow-card); overflow: hidden; cursor: pointer; transition: transform 160ms ease-out, box-shadow 160ms ease-out; }
.tutorial-card:hover { transform: translateY(-2px); box-shadow: var(--shadow-card-hover); }
.tutorial-card:active { transform: scale(0.98); }

.card-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 20px 20px 14px; border-bottom: 1px solid var(--color-border); }
.card-head h2 { margin: 0; font-size: 18px; font-weight: 700; }
.card-stars { color: #e8a317; font-size: 15px; letter-spacing: 1px; white-space: nowrap; }
.card-head .card-stars { font-size: 14px; }

.card-body { display: flex; gap: 16px; padding: 16px 20px 20px; }
.card-body img { width: 140px; height: 100px; object-fit: cover; border-radius: 10px; flex-shrink: 0; background: var(--color-surface-warm); }
.card-body p { margin: 0; color: var(--color-text-muted); font-size: 14px; line-height: 1.65; white-space: pre-wrap; }

/* Lightbox */
.lightbox-overlay { position: fixed; inset: 0; z-index: 100; display: flex; align-items: center; justify-content: center; padding: 32px; }
.lightbox-card { position: relative; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 18px; box-shadow: 0 32px 64px rgba(116, 72, 20, 0.16); max-width: 1024px; width: 100%; max-height: 85vh; overflow-y: auto; }
.lightbox-card .card-head { padding: 32px 32px 20px; border-bottom: 1px solid var(--color-border); }
.lightbox-card .card-head h2 { font-size: 26px; }
.lightbox-card .card-head .card-stars { font-size: 18px; }
.lightbox-card .card-body { padding: 24px 32px 32px; gap: 24px; }
.lightbox-card .card-body img { width: 352px; height: auto; max-height: 55vh; object-fit: contain; border-radius: 14px; }
.lightbox-card .card-body p { font-size: 16px; white-space: pre-wrap; }

/* Transition */
.lightbox-enter-active { transition: opacity 240ms ease-out; }
.lightbox-leave-active { transition: opacity 200ms ease-in; }
.lightbox-enter-from, .lightbox-leave-to { opacity: 0; }
.lightbox-enter-active .lightbox-card { transition: transform 280ms cubic-bezier(0.34, 1.56, 0.64, 1), opacity 240ms ease-out; }
.lightbox-leave-active .lightbox-card { transition: transform 180ms ease-in, opacity 200ms ease-in; }
.lightbox-enter-from .lightbox-card { transform: scale(0.92); opacity: 0; }
.lightbox-leave-to .lightbox-card { transform: scale(0.95); opacity: 0; }

@media (max-width: 767px) {
  .content { width: min(100% - 32px, 1280px); padding-bottom: 48px; }
  .page-title { font-size: 28px; }
  .page-description { font-size: 14px; }
  .filter-bar { flex-direction: column; align-items: stretch; gap: 14px; }
  .search-label input { width: 100%; }
  .card-grid { grid-template-columns: 1fr; }
  .card-body img { width: 100px; height: 72px; }
  .lightbox-overlay { padding: 12px; align-items: flex-start; }
  .lightbox-card { max-height: 92vh; }
  .lightbox-card .card-head { padding: 20px 20px 14px; }
  .lightbox-card .card-head h2 { font-size: 19px; }
  .lightbox-card .card-head .card-stars { font-size: 14px; }
  .lightbox-card .card-body { flex-direction: column; padding: 14px 20px 20px; gap: 16px; }
  .lightbox-card .card-body img { width: 100%; max-height: 40vh; }
  .lightbox-card .card-body p { font-size: 14px; }
}

@media (max-width: 480px) {
  .content { width: min(100% - 24px, 1280px); }
  .card-head { padding: 16px 16px 12px; }
  .card-head h2 { font-size: 16px; }
  .card-head .card-stars { font-size: 13px; }
  .card-body { padding: 12px 16px 16px; gap: 12px; }
  .card-body img { width: 80px; height: 60px; }
  .card-body p { font-size: 13px; }
  .lightbox-card .card-head { padding: 16px 16px 12px; }
  .lightbox-card .card-head h2 { font-size: 17px; }
  .lightbox-card .card-body { padding: 12px 16px 16px; }
}
</style>
