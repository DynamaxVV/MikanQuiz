<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import BrandHeader from '@/components/BrandHeader.vue';
import ErrorPanel from '@/components/ErrorPanel.vue';
import QuestionMedia from '@/components/QuestionMedia.vue';
import { useAttempt } from '@/composables/useAttempt';
import { useFontRendering } from '@/composables/useFontRendering';
import type { AnswerKey } from '@/types';

const route = useRoute();
const router = useRouter();
const { attempt, answers, error, loading, submitting, completed, clearSavedAttempt, restore, selectAnswer, submit } = useAttempt();
const { fontStyle } = useFontRendering();
const currentIndex = ref(0);
const missingNotice = ref('');
const displayName = computed(() => localStorage.getItem('hanzipen-display-name')?.trim() ?? '');
const currentQuestion = computed(() => attempt.value?.questions[currentIndex.value] ?? null);
const total = computed(() => attempt.value?.questions.length ?? 0);
const answeredCount = computed(() => Object.keys(answers.value).length);
const modeLabel = computed(() => ({ beginner: '新手级', proficient: '熟练级', challenge: '挑战级' }[attempt.value?.mode ?? 'beginner']));

function previous(): void { currentIndex.value = Math.max(0, currentIndex.value - 1); missingNotice.value = ''; }
function next(): void { currentIndex.value = Math.min(total.value - 1, currentIndex.value + 1); missingNotice.value = ''; }

function choose(answer: AnswerKey): void {
  if (!currentQuestion.value) return;
  selectAnswer(currentQuestion.value.id, answer);
  missingNotice.value = '';
}

async function submitAnswers(): Promise<void> {
  if (!attempt.value) return;
  if (!completed.value) {
    const incomplete = attempt.value.questions
      .map((question, index) => (!answers.value[question.id] ? index + 1 : null))
      .filter((value): value is number => value !== null);
    missingNotice.value = `还有第 ${incomplete.join('、')} 题没有选择答案。`;
    return;
  }
  try {
    const result = await submit(displayName.value);
    sessionStorage.setItem(`hanzipen-result-${result.submissionId}`, JSON.stringify(result));
    await router.push(`/result/${encodeURIComponent(result.submissionId)}`);
  } catch { /* Error message stays next to the submit action. */ }
}

function onKeydown(event: KeyboardEvent): void {
  const target = event.target as HTMLElement | null;
  if (target?.matches('input, textarea, select, [contenteditable="true"]')) return;
  if (event.key === 'ArrowLeft') { event.preventDefault(); previous(); }
  if (event.key === 'ArrowRight') { event.preventDefault(); next(); }
}

async function loadAttempt(): Promise<void> {
  const restored = await restore();
  if (restored && restored.id !== route.params.attempt) {
    await router.replace(`/quiz/${encodeURIComponent(restored.id)}`);
  }
}

function restart(): void {
  clearSavedAttempt();
  void router.push('/levels');
}

onMounted(() => { void loadAttempt(); window.addEventListener('keydown', onKeydown); });
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown));
</script>

<template>
  <main class="quiz-page">
    <div class="content">
      <BrandHeader />
      <div v-if="loading" class="loading-card card">正在恢复本次练习…</div>
      <ErrorPanel v-else-if="error && !attempt" :message="error" @retry="loadAttempt" />
      <section v-else-if="attempt && currentQuestion" aria-labelledby="quiz-title">
        <header class="quiz-header">
          <RouterLink class="exit" to="/levels">← 退出练习</RouterLink>
          <div class="quiz-status">
            <span id="quiz-title">{{ modeLabel }} · 第 {{ currentIndex + 1 }} / {{ total }} 题</span>
            <span class="sr-only" aria-live="polite">当前为第 {{ currentIndex + 1 }} 题，共 {{ total }} 题。</span>
          </div>
          <div class="progress" :aria-label="`已完成 ${answeredCount} / ${total} 题`"><span :style="{ width: `${(answeredCount / total) * 100}%` }"></span></div>
        </header>
        <div class="quiz-layout">
          <section class="question-panel card">
            <p class="eyebrow">第 {{ currentIndex + 1 }} 题</p>
            <h1>{{ currentQuestion.text }}</h1>
            <QuestionMedia class="quiz-media" :image-url="currentQuestion.imageUrl" :text="currentQuestion.text" />
          </section>
          <section class="answer-panel" aria-label="答案选项">
            <div class="answers" role="radiogroup" :aria-label="`${currentQuestion.text}的选项`"><section v-for="group in currentQuestion.optionGroups" :key="group.id" class="option-group"><h2>{{ group.name }}</h2><button v-for="option in group.options" :key="option.id" type="button" :style="fontStyle(option)" :class="{ selected: answers[currentQuestion.id] === option.id }" @click="choose(option.id)">{{ option.name }}</button></section></div>
            <p v-if="missingNotice" class="status-info" role="status">{{ missingNotice }}</p>
            <p v-if="error" class="status-error" role="alert">{{ error }}</p>
            <div class="question-navigation">
              <button type="button" class="secondary" :disabled="currentIndex === 0" @click="previous">上一题</button>
              <button v-if="currentIndex < total - 1" type="button" class="primary" @click="next">下一题</button>
              <button v-else type="button" class="primary" :disabled="submitting" @click="submitAnswers">{{ submitting ? '正在提交…' : '提交答案' }}</button>
            </div>
            <div class="restart-row"><button type="button" class="restart" @click="restart">重新开始本次练习</button></div>
          </section>
        </div>
      </section>
      <section v-else class="card missing-attempt">
        <h1 class="page-title">没有可恢复的练习</h1>
        <p>这次练习可能已经提交或超过 24 小时。请重新选择难度开始。</p>
        <RouterLink to="/levels">选择难度</RouterLink>
      </section>
    </div>
  </main>
</template>

<style scoped>
.quiz-page { min-height: 100vh; background: var(--color-bg); }
.content { width: min(1280px, calc(100% - clamp(48px, 8vw, 128px))); margin: 0 auto; }
.loading-card, .missing-attempt { margin-top: 50px; padding: 32px; }
.missing-attempt p { color: var(--color-text-muted); line-height: 1.65; }
.missing-attempt a, .exit, .restart { color: var(--color-action); font-weight: 650; }
.quiz-header { display: grid; min-height: 70px; grid-template-columns: 1fr auto 1fr; align-items: center; gap: 20px; border-bottom: 1px solid var(--color-border); }
.quiz-status { font-size: 14px; font-weight: 700; white-space: nowrap; }
.progress { justify-self: end; width: min(210px, 18vw); height: 8px; overflow: hidden; border-radius: 999px; background: #f0dfcc; }
.progress span { display: block; height: 100%; border-radius: inherit; background: var(--color-action); transition: width 160ms ease-out; }
.quiz-layout { display: grid; grid-template-columns: minmax(0, 7fr) minmax(340px, 5fr); gap: 28px; padding: 28px 0 64px; }
.question-panel { padding: 28px; }
.question-panel h1 { margin: 0 0 24px; font-size: clamp(23px, 2.2vw, 32px); line-height: 1.3; letter-spacing: -.015em; }
.quiz-media :deep(.image-button) { height: min(42vh, 360px); }
.answer-panel { position: sticky; top: 18px; align-self: start; padding: 8px 0; }
.answers { display: grid; gap: 12px; }
.option-group { padding: 8px 16px; border: 1px solid var(--color-border); border-radius: 16px; background: #fffdf9; }
.option-group h2 { margin: 0 0 6px; color: #85451e; font-size: 17px; }
.option-group button { display: inline-flex; align-items: center; justify-content: center; margin: 0 8px 8px 0; border: 1px solid transparent; border-radius: 12px; padding: 0 9px; height: 42px; line-height: 1; color: var(--color-text-muted); background: var(--color-surface-warm); font: inherit; font-size: 13px; font-weight: 650; cursor: pointer; transition: border-color 120ms ease-out, background 120ms ease-out; }
.option-group button:hover { border-color: #edcfac; color: #85451e; background: #fff8ed; }
.option-group button.selected { border-color: #d58a45; color: #85451e; background: #fff0d8; }
.option-group button:focus-visible { outline: 3px solid rgba(213, 138, 69, .3); outline-offset: 2px; }
.question-navigation { display: flex; justify-content: space-between; gap: 12px; margin-top: 24px; }
.primary, .secondary { min-height: 46px; border-radius: var(--radius-button); padding: 0 20px; font-weight: 700; }
.primary { border: 1px solid var(--color-action); color: #fff; background: var(--color-action); }
.primary:hover { background: var(--color-action-hover); }
.secondary { border: 1px solid var(--color-border); color: var(--color-text); background: var(--color-surface); }
.primary:disabled, .secondary:disabled { opacity: .55; }
.restart-row { display: flex; justify-content: flex-end; margin-top: 14px; }
.restart { border: 0; padding: 4px 0; background: transparent; font-size: 13px; }
.restart:hover { color: var(--color-action-hover); text-decoration: underline; }
@media (max-width: 1023px) { .quiz-layout { grid-template-columns: 1fr; }.answer-panel { position: static; }.progress { width: 160px; } }
@media (max-width: 767px) { .content { width: min(100% - 32px, 1280px); }.quiz-header { grid-template-columns: 1fr auto; padding: 10px 0; }.quiz-status { grid-row: 2; }.progress { grid-row: 2; width: 120px; }.question-panel { padding: 20px; }.quiz-layout { padding-top: 16px; } }
@media (prefers-reduced-motion: reduce) { .progress span { transition: none; } }
</style>
