<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue';
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
const { fontError, fontState, fontStyle, preloadFonts } = useFontRendering();
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

const difficultyCap = computed(() => ({ beginner: 1, proficient: 2, challenge: 3 }[attempt.value?.mode ?? 'challenge']));

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
const previewState = computed(() => previewFont.value ? fontState(previewFont.value) : 'idle');
let pressTimer: ReturnType<typeof setTimeout> | null = null;
let didLongPress = false;

function onOptionPointerDown(option: FontOption, event: PointerEvent): void {
  if (!option.fontUrl) { fontError.value = '该字体尚未上传字体文件，无法预览。'; return; }
  preloadFonts([option]);
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


const questionMap = ref<HTMLDialogElement | null>(null);
const questionMapOpen = ref(false);
const questionMapPosition = ref({ top: '0px', right: '16px' });

async function openQuestionMap(event: MouseEvent): Promise<void> {
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
  questionMapPosition.value = { top: `${rect.bottom + 8}px`, right: `${Math.max(16, document.documentElement.clientWidth - rect.right)}px` };
  questionMapOpen.value = true;
  questionMap.value?.showModal();
  await nextTick();
  questionMap.value?.querySelector<HTMLButtonElement>('[aria-current="step"]')?.focus();
}

function jumpToQuestion(index: number): void {
  currentIndex.value = index;
  missingNotice.value = '';
  questionMap.value?.close();
  scrollToTop();
}

function closeMapOnBackdrop(event: MouseEvent): void {
  const dialog = questionMap.value;
  if (!dialog || event.target !== dialog) return;
  const rect = dialog.getBoundingClientRect();
  if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();
}

function moveMapFocus(event: KeyboardEvent, index: number): void {
  const movement: Record<string, number> = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -5, ArrowDown: 5 };
  let target: number;
  if (event.key === 'Home') target = 0;
  else if (event.key === 'End') target = total.value - 1;
  else if (event.key in movement) target = Math.max(0, Math.min(total.value - 1, index + movement[event.key]));
  else return;
  event.preventDefault();
  questionMap.value?.querySelectorAll<HTMLButtonElement>('.question-map-number')[target]?.focus();
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
  if (questionMapOpen.value) return;
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
      <BrandHeader show-feedback feedback-source="quiz" />
      <div v-if="loading" class="loading-card card">正在恢复本次练习…</div>
      <ErrorPanel v-else-if="error && !attempt" :message="error" @retry="loadAttempt" />
      <section v-else-if="attempt && currentQuestion" aria-labelledby="quiz-title">
        <header class="quiz-header">
          <RouterLink class="exit" to="/levels">← 退出练习</RouterLink>
          <div class="quiz-status">
            <span id="quiz-title">{{ modeLabel }} · 第 {{ currentIndex + 1 }} / {{ total }} 题</span>
            <span class="sr-only" aria-live="polite">当前为第 {{ currentIndex + 1 }} 题，共 {{ total }} 题。</span>
          </div>
          <button class="question-map-trigger" type="button" aria-haspopup="dialog" aria-controls="question-map" :aria-expanded="questionMapOpen" :aria-label="`打开答题卡，已答 ${answeredCount} / ${total} 题`" @click="openQuestionMap">
            <span>题号 · 已答 {{ answeredCount }}/{{ total }}</span><span class="question-map-icon" aria-hidden="true">▦</span>
            <span class="question-map-mini" aria-hidden="true"><i v-for="(question, index) in attempt.questions" :key="question.id" :class="{ answered: !!answers[question.id], current: index === currentIndex }"></i></span>
          </button>
          <dialog id="question-map" ref="questionMap" class="question-map" :style="questionMapPosition" aria-labelledby="question-map-title" @close="questionMapOpen = false" @click="closeMapOnBackdrop">
            <div class="question-map-heading"><h2 id="question-map-title">答题卡 <span>已答 {{ answeredCount }} / {{ total }}</span></h2><button type="button" class="question-map-close" aria-label="关闭答题卡" @click="questionMap?.close()">×</button></div>
            <nav class="question-map-grid" aria-label="按题号切换">
              <button v-for="(question, index) in attempt.questions" :key="question.id" type="button" class="question-map-number" :class="{ answered: !!answers[question.id], current: index === currentIndex }" :aria-current="index === currentIndex ? 'step' : undefined" :aria-label="`第 ${index + 1} 题，${answers[question.id] ? '已答' : '未答'}${index === currentIndex ? '，当前题' : ''}`" @click="jumpToQuestion(index)" @keydown="moveMapFocus($event, index)">{{ index + 1 }}<span v-if="answers[question.id]" aria-hidden="true">✓</span></button>
            </nav>
            <p class="question-map-legend"><span><i class="current"></i>当前题</span><span><i class="answered"></i>已答</span><span><i></i>未答</span></p>
            <p class="question-map-hint">点击题号切题，已选答案会保留。</p>
          </dialog>
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
            <div class="answers" role="group" :aria-label="`${currentQuestion.text}的选项`"><section v-for="group in filteredGroups" :key="group.id" class="option-group"><h2>{{ group.name }}</h2><button v-for="option in group.options" :key="option.id" type="button" :aria-pressed="answers[currentQuestion.id] === option.id" :style="fontRenderEnabled ? fontStyle(option) : undefined" :class="{ selected: answers[currentQuestion.id] === option.id }" @pointerdown="onOptionPointerDown(option, $event)" @pointerup="onOptionPointerUp" @pointerleave="onOptionPointerLeave" @pointercancel="onOptionPointerUp" @click="chooseWithGuard(option.id)">{{ option.name }}</button></section></div>
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
      :style="{ left: previewLeft + 'px', ...(previewAbove ? { bottom: previewBottom + 'px' } : { top: previewTop + 'px' }) }"
    ><span v-if="previewState === 'loading' || previewState === 'idle'" class="font-preview-loading" aria-label="字体加载中"><i></i>字体加载中</span><span v-else-if="previewState === 'ready'" :style="{ ...fontStyle(previewFont), fontSize: '200%' }">{{ previewFont.name }}</span><span v-else class="font-preview-failed">字体加载失败</span></div>
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
.question-map-trigger { justify-self: end; display: grid; grid-template-columns: 1fr auto; align-items: center; gap: 5px 10px; width: 150px; min-height: 42px; border: 1px solid #ead8c1; border-radius: 10px; padding: 7px 11px; background: var(--color-surface); color: var(--color-action); font-size: 12px; font-weight: 650; }
.question-map-trigger:hover { background: var(--color-surface-warm); }
.question-map-icon { grid-column: 2; grid-row: 1 / 3; font-size: 18px; }
.question-map-mini { display: flex; gap: 2px; min-width: 0; }
.question-map-mini i { flex: 1; min-width: 0; height: 3px; border: 1px solid #d9c8b2; border-radius: 1px; background: var(--color-surface); }
.question-map-mini i.answered { background: #dca260; border-color: #dca260; }
.question-map-mini i.current { outline: 1px solid var(--color-action); outline-offset: 1px; }
.question-map { position: fixed; left: auto; bottom: auto; width: min(340px, calc(100vw - 32px)); max-width: none; max-height: calc(100dvh - 120px); margin: 0; padding: 18px; border: 1px solid #e0c9ab; border-radius: 16px; background: #fffdf9; color: var(--color-text); box-shadow: 0 12px 35px rgba(71, 48, 24, .14); }
.question-map::backdrop { background: transparent; }
.question-map-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
.question-map-heading h2 { margin: 0; font-size: 16px; }
.question-map-heading h2 span { margin-left: 8px; color: var(--color-text-muted); font-size: 12px; font-weight: 500; }
.question-map-close { display: grid; place-items: center; min-width: 36px; min-height: 36px; border: 0; border-radius: 8px; background: transparent; color: var(--color-text-muted); font-size: 24px; }
.question-map-close:hover { background: var(--color-surface-accent); }
.question-map-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 8px; }
.question-map-number { position: relative; min-width: 0; min-height: 44px; border: 1px solid #eadccc; border-radius: 8px; background: var(--color-surface); color: var(--color-text-muted); font-size: 14px; font-weight: 650; }
.question-map-number.answered { border-color: #ecd5b7; background: var(--color-surface-accent); color: #85451e; }
.question-map-number.current { outline: 2px solid var(--color-action); outline-offset: 0; color: var(--color-action); }
.question-map-number:focus-visible { outline: 3px solid var(--color-focus); outline-offset: 2px; }
.question-map-number:hover { border-color: var(--color-action); }
.question-map-number > span { position: absolute; top: 4px; right: 5px; font-size: 9px; }
.question-map-legend { display: flex; justify-content: space-between; gap: 8px; margin: 16px 0 0; color: var(--color-text-muted); font-size: 11px; }
.question-map-legend span { display: inline-flex; align-items: center; gap: 5px; }
.question-map-legend i { width: 10px; height: 10px; border: 1px solid #d9c8b2; border-radius: 2px; background: var(--color-surface); }
.question-map-legend i.current { border: 2px solid var(--color-action); }
.question-map-legend i.answered { background: var(--color-surface-accent); border-color: #dca260; }
.question-map-hint { margin: 12px 0 0; color: var(--color-text-muted); font-size: 11px; line-height: 1.6; }
@media (max-width: 767px) {
  .question-map-trigger { grid-row: 2; grid-column: 2; width: 142px; }
  .question-map { top: auto !important; right: 0 !important; bottom: 0; left: 0; width: 100%; max-height: 75dvh; padding: 16px 20px max(20px, env(safe-area-inset-bottom)); border-radius: 20px 20px 0 0; }
  .question-map::backdrop { background: rgba(51, 39, 24, .16); }
  .question-map-close { min-width: 44px; min-height: 44px; }
}
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
.font-preview-loading { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; }.font-preview-loading i { width: 14px; height: 14px; border: 2px solid rgba(255,255,255,.35); border-top-color: #fff; border-radius:50%; animation: font-loading-spin .7s linear infinite; }.font-preview-failed { color: #ffd5cd; font-size: 13px; }@keyframes font-loading-spin { to { transform: rotate(360deg); } }@media (prefers-reduced-motion: reduce) { .font-preview-loading i { animation: none; } }
</style>
