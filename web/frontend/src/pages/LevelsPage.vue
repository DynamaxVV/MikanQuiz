<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { api } from '@/api/client';
import BrandHeader from '@/components/BrandHeader.vue';
import ErrorPanel from '@/components/ErrorPanel.vue';
import { useAttempt } from '@/composables/useAttempt';
import type { DifficultyMode, QuizSettings } from '@/types';

const router = useRouter();
const { create, error: attemptError, loading: attemptLoading } = useAttempt();
const loading = ref(true);
const error = ref('');
const settings = ref<QuizSettings | null>(null);
const starting = ref<DifficultyMode | null>(null);
const levels: { key: DifficultyMode; title: string; subtitle: string; icon: string }[] = [
  { key: 'beginner', title: '新手级', subtitle: '从基础字形开始', icon: '新' },
  { key: 'proficient', title: '熟练级', subtitle: '平衡观察与判断', icon: '熟' },
  { key: 'challenge', title: '挑战级', subtitle: '挑战容易混淆的字形', icon: '挑' },
];

async function load(): Promise<void> {
  loading.value = true;
  error.value = '';
  try { settings.value = await api.getQuizSettings(); }
  catch (caught) { error.value = caught instanceof Error ? caught.message : '难度设置加载失败。'; }
  finally { loading.value = false; }
}

async function selectLevel(mode: DifficultyMode): Promise<void> {
  starting.value = mode;
  try {
    const attempt = await create(mode);
    await router.push(`/quiz/${encodeURIComponent(attempt.id)}`);
  } catch { /* composable already preserves a visible error. */ }
  finally { starting.value = null; }
}

onMounted(load);
</script>

<template>
  <main class="levels-page">
    <div class="content">
      <BrandHeader />
      <section class="levels-layout" aria-labelledby="levels-title">
        <div class="intro">
          <p class="eyebrow">选择难度</p>
          <h1 id="levels-title" class="page-title">从哪一组字形开始？</h1>
          <p class="page-description">每次会抽取 {{ settings?.questionCount ?? '—' }} 道题，快开始吧~</p>
          <RouterLink class="back-link" to="/">← 返回首页</RouterLink>
        </div>
        <div v-if="loading" class="loading-card card">正在读取难度设置…</div>
        <ErrorPanel v-else-if="error" :message="error" @retry="load" />
        <div v-else class="level-list">
          <button v-for="level in levels" :key="level.key" class="level-card" type="button" :disabled="attemptLoading" @click="selectLevel(level.key)">
            <span class="level-icon">{{ level.icon }}</span>
            <span class="level-copy"><strong>{{ level.title }}</strong><small>{{ level.subtitle }}</small></span>
            <span v-if="starting === level.key" class="pending">正在准备…</span>
            <span v-else class="arrow" aria-hidden="true">→</span>
          </button>
        </div>
      </section>
      <section v-if="attemptError" class="attempt-error" role="alert">{{ attemptError }}</section>
    </div>
  </main>
</template>

<style scoped>
.levels-page { min-height: 100vh; background: var(--color-bg); }
.content { width: min(1280px, calc(100% - clamp(48px, 8vw, 128px))); margin: 0 auto; }
.levels-layout { display: grid; grid-template-columns: minmax(260px, 4fr) minmax(440px, 8fr); gap: clamp(40px, 7vw, 96px); padding: 72px 0; }
.intro { max-width: 390px; }
.back-link { display: inline-block; margin-top: 28px; color: var(--color-action); font-weight: 650; }
.level-list { display: grid; gap: 16px; }
.level-card { display: grid; min-height: 122px; grid-template-columns: 58px 1fr auto; align-items: center; gap: 18px; padding: 20px 24px; border: 1px solid var(--color-border); border-radius: 22px; color: var(--color-text); background: var(--color-surface); box-shadow: var(--shadow-card); text-align: left; transition: transform 100ms ease-out, box-shadow 160ms ease-out; }
.level-card:hover { transform: translateY(-2px); box-shadow: var(--shadow-card-hover); }
.level-card:active { transform: scale(.985); }
.level-icon { display: grid; width: 52px; height: 52px; place-items: center; border-radius: 16px; color: var(--color-action); background: var(--color-surface-accent); font-size: 22px; font-weight: 750; }
.level-copy strong { display: block; font-size: 21px; }.level-copy small { display: block; margin-top: 7px; color: var(--color-text-muted); font-size: 15px; }
.arrow { font-size: 28px; }.pending { color: var(--color-text-muted); font-size: 14px; }.loading-card { padding: 32px; color: var(--color-text-muted); }
.attempt-error { margin: -42px 0 48px; border: 1px solid #ecc3be; border-radius: 12px; padding: 14px 16px; color: #7d2f2a; background: #fff0ee; line-height: 1.55; }
@media (max-width: 1023px) { .levels-layout { grid-template-columns: 1fr; gap: 34px; padding-top: 40px; } .intro { max-width: 680px; } }
@media (max-width: 767px) { .content { width: min(100% - 32px, 1280px); } .level-card { padding: 18px; } }
@media (prefers-reduced-motion: reduce) { .level-card:hover, .level-card:active { transform: none; } }
</style>
