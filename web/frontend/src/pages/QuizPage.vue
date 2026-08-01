<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import BrandHeader from '@/components/BrandHeader.vue';
import ErrorPanel from '@/components/ErrorPanel.vue';
import QuestionMedia from '@/components/QuestionMedia.vue';
import { useAttempt } from '@/composables/useAttempt';
import { useFontRendering } from '@/composables/useFontRendering';
import type { AnswerKey, FontOption } from '@/types';

const route = useRoute();
const router = useRouter();
const { attempt, answers, error, loading, submitting, completed, clearSavedAttempt, restore, selectAnswer, submit } = useAttempt();
const { fontError, fontStyle, preloadFonts } = useFontRendering();
const currentIndex = ref(0);
const missingNotice = ref('');
const displayName = computed(() => localStorage.getItem('hanzipen-display-name')?.trim() ?? '');
const currentQuestion = computed(() => attempt.value?.questions[currentIndex.value] ?? null);
const total = computed(() => attempt.value?.questions.length ?? 0);
const answeredCount = computed(() => Object.keys(answers.value).length);
const modeLabel = computed(() => ({ beginner: '新手级', proficient: '熟练级', challenge: '挑战级' }[attempt.value?.mode ?? 'beginner']));

const answerPanelRef = ref<HTMLElement | null>(null);
const imageMaxHeight = ref('540px');

function syncImageHeight(): void {
  if (!answerPanelRef.value) return;
  const answerHeight = answerPanelRef.value.getBoundingClientRect().height;
  if (answerHeight > 0) imageMaxHeight.value = `${Math.round(answerHeight * 0.75)}px`;
}

const fontRenderEnabled = ref(localStorage.getItem('hanzipen-font-render') === '1');

const difficultyCap = computed(() => currentQuestion.value?.difficulty ?? 3);

const filteredGroups = computed(() => {
  if (!currentQuestion.value) return [];
  return currentQuestion.value.optionGroups.map((group) => ({
    ...group,
    options: group.options.filter((option) => option.minimumDifficulty <= difficultyCap.value),
  })).filter((group) => group.options.length > 0);
});

function toggleFontRender(): void {
  fontRenderEnabled.value = !fontRenderEnabled.value;
  localStorage.setItem('hanzipen-font-render', fontRenderEnabled.value ? '1' : '0');
  if (!fontRenderEnabled.value) return;
  const options = filteredGroups.value.flatMap((group) => group.options).filter((option) => option.fontUrl);
  if (!options.length) { fontError.value = '当前题目没有已上传的字体文件，无法即时渲染。'; return; }
  preloadFonts(options);
}

const previewFont = ref<FontOption | null>(null);
const previewAbove = ref(false);
const previewLeft = ref(0);
const previewBottom = ref(0);
const previewTop = ref(0);
let pressTimer: ReturnType<typeof setTimeout> | null = null;
let didLongPress = false;

function onOptionPointerDown(option: FontOption, event: PointerEvent): void {
  if (!option.fontUrl) { fontError.value = '该字体尚未上传字体文件，无法预览。'; return; }
  didLongPress = false;
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
  const above = rect.top > window.innerHeight / 2;
  pressTimer = setTimeout(() => {
    didLongPress = true;
    previewAbove.value = above;
    previewLeft.value = rect.left + rect.width / 2;
    if (above) {
      previewBottom.value = window.innerHeight - rect.top;
    } else {
      previewTop.value = rect.bottom;
    }
    previewFont.value = option;
  }, 500);
}

function onOptionPointerUp(): void {
  if (pressTimer) { clearTimeout(pressTimer); pressTimer = null; }
  previewFont.value = null;
}

function onOptionPointerLeave(): void {
  if (pressTimer) { clearTimeout(pressTimer); pressTimer = null; }
  previewFont.value = null;
}

function chooseWithGuard(optionId: string): void {
  if (didLongPress) return;
  choose(optionId);
}


function previous(): void { currentIndex.value = Math.max(0, currentIndex.value - 1); missingNotice.value = ''; scrollToTop(); }
function next(): void { currentIndex.value = Math.min(total.value - 1, currentIndex.value + 1); missingNotice.value = ''; scrollToTop(); }

function scrollToTop(): void {
  if (window.innerWidth > 1023) return;
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

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

onMounted(() => { void loadAttempt(); window.addEventListener('keydown', onKeydown); syncImageHeight(); window.addEventListener('resize', syncImageHeight); });
onBeforeUnmount(() => { window.removeEventListener('keydown', onKeydown); window.removeEventListener('resize', syncImageHeight); });
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
            <QuestionMedia class="quiz-media" :image-url="currentQuestion.imageUrl" :text="currentQuestion.text" :style="{ '--quiz-media-max-h': imageMaxHeight }" />
          </section>
          <section ref="answerPanelRef" class="answer-panel" aria-label="答案选项">
            <label class="font-render-toggle" @click.prevent="toggleFontRender">
              <span class="toggle-label">即时渲染字体</span>
              <span class="toggle-track" :class="{ on: fontRenderEnabled }" role="switch" :aria-checked="fontRenderEnabled" tabindex="0">
                <span class="toggle-thumb"></span>
              </span>
            </label>
            <div class="answers" role="radiogroup" :aria-label="`${currentQuestion.text}的选项`"><section v-for="group in filteredGroups" :key="group.id" class="option-group"><h2>{{ group.name }}</h2><button v-for="option in group.options" :key="option.id" type="button" :style="fontRenderEnabled ? fontStyle(option) : undefined" :class="{ selected: answers[currentQuestion.id] === option.id }" @pointerdown="onOptionPointerDown(option, $event)" @pointerup="onOptionPointerUp" @pointerleave="onOptionPointerLeave" @pointercancel="onOptionPointerUp" @click="chooseWithGuard(option.id)">{{ option.name }}</button></section></div>
            <p class="font-preview-tips">长按字体选项可预览字体效果</p>
            <p v-if="fontError" class="status-error" role="status">{{ fontError }}</p>
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

  <Teleport to="body">
    <div
      v-if="previewFont"
      class="font-preview-tooltip"
      :style="{
        ...fontStyle(previewFont),
        left: previewLeft + 'px',
        fontSize: '200%',
        ...(previewAbove ? { bottom: previewBottom + 'px' } : { top: previewTop + 'px' }),
      }"
    >{{ previewFont.name }}</div>
  </Teleport>
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
.quiz-media :deep(.image-button) { height: min(56vh, var(--quiz-media-max-h, 520px)); }
.answer-panel { position: sticky; top: 18px; align-self: start; padding: 8px 0; }
.answers { display: grid; gap: 8px; }
.option-group { padding: 6px 12px; border: 1px solid var(--color-border); border-radius: 14px; background: #fffdf9; }
.option-group h2 { margin: 0 0 4px; color: #85451e; font-size: 14px; }
.option-group button { display: inline-flex; align-items: center; justify-content: center; margin: 0 5px 5px 0; border: 1px solid transparent; border-radius: 10px; padding: 0 7px; height: 34px; line-height: 1; color: var(--color-text-muted); background: var(--color-surface-warm); font: inherit; font-size: 13px; font-weight: 650; cursor: pointer; transition: border-color 120ms ease-out, background 120ms ease-out; user-select: none; -webkit-user-select: none; -webkit-touch-callout: none; touch-action: manipulation; }
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
@media (max-width: 1023px) { .quiz-layout { grid-template-columns: 1fr; }.answer-panel { position: static; }.progress { width: 160px; }.quiz-media :deep(.image-button) { height: min(38vh, var(--quiz-media-max-h, 300px)); } }
@media (max-width: 767px) { .content { width: min(100% - 32px, 1280px); }.quiz-header { grid-template-columns: 1fr auto; padding: 10px 0; }.quiz-status { grid-row: 2; }.progress { grid-row: 2; width: 120px; }.question-panel { padding: 20px; }.quiz-layout { padding-top: 16px; } }
@media (prefers-reduced-motion: reduce) { .progress span { transition: none; } }

.font-preview-tips { margin: 10px 0 0; color: var(--color-text-muted); font-size: 12px; text-align: center; }

.font-render-toggle {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  margin-bottom: 14px;
  cursor: pointer;
  user-select: none;
}
.toggle-label { color: var(--color-text-muted); font-size: 12px; font-weight: 650; }
.toggle-track {
  position: relative;
  width: 44px;
  height: 26px;
  border-radius: 999px;
  background: #e3d7c7;
  cursor: pointer;
  transition: background 160ms ease-out;
  outline: none;
}
.toggle-track:focus-visible { outline: 3px solid var(--color-focus); outline-offset: 2px; }
.toggle-track.on { background: var(--color-action); }
.toggle-thumb {
  position: absolute;
  top: 3px;
  left: 3px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 1px 3px rgba(73, 48, 26, 0.16);
  transition: transform 180ms cubic-bezier(0.34, 1.56, 0.64, 1);
}
.toggle-track.on .toggle-thumb { transform: translateX(18px); }

.font-preview-tooltip {
  position: fixed;
  z-index: 200;
  transform: translateX(-50%);
  padding: 8px 18px;
  border-radius: 14px;
  color: #fff;
  background: rgba(73, 48, 26, 0.92);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  font-weight: 700;
  letter-spacing: 0.02em;
  white-space: nowrap;
  pointer-events: none;
  box-shadow: 0 6px 20px rgba(73, 48, 26, 0.18);
}
</style>
