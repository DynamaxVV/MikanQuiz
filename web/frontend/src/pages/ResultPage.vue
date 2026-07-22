<script setup lang="ts">
import { computed, ref } from 'vue';
import { useRoute } from 'vue-router';
import AnswerOption from '@/components/AnswerOption.vue';
import BrandHeader from '@/components/BrandHeader.vue';
import QuestionMedia from '@/components/QuestionMedia.vue';
import type { SubmissionResult } from '@/types';

const route = useRoute();
const raw = sessionStorage.getItem(`hanzipen-result-${route.params.attempt}`);
const result = ref<SubmissionResult | null>(raw ? JSON.parse(raw) as SubmissionResult : null);
const reviewIndex = ref(0);
const currentWrong = computed(() => result.value?.wrongAnswers[reviewIndex.value] ?? null);
const modeLabel = computed(() => ({ beginner: '新手级', proficient: '熟练级', challenge: '挑战级' }[result.value?.mode ?? 'beginner']));
</script>

<template>
  <main class="result-page">
    <div class="content"><BrandHeader />
      <section v-if="result" class="result-layout" aria-labelledby="result-title">
        <aside class="score-panel card">
          <p class="eyebrow">已完成</p>
          <h1 id="result-title">{{ result.score }} 分</h1>
          <p class="score-detail">{{ result.correctCount }} / {{ result.totalCount }} 题正确</p>
          <dl><div><dt>难度</dt><dd>{{ modeLabel }}</dd></div><div v-if="result.displayName"><dt>昵称</dt><dd>{{ result.displayName }}</dd></div></dl>
          <RouterLink class="retry" to="/levels">再答一次</RouterLink>
        </aside>
        <section class="review-panel">
          <template v-if="currentWrong">
            <header class="review-header"><div><p class="eyebrow">错题 {{ reviewIndex + 1 }} / {{ result.wrongAnswers.length }}</p><h2>{{ currentWrong.questionText }}</h2></div><div class="review-controls"><button :disabled="reviewIndex === 0" @click="reviewIndex -= 1">上一题</button><button :disabled="reviewIndex === result.wrongAnswers.length - 1" @click="reviewIndex += 1">下一题</button></div></header>
            <QuestionMedia v-if="currentWrong.imageUrl" :image-url="currentWrong.imageUrl" :text="currentWrong.questionText" />
            <div v-if="Object.keys(currentWrong.options).length" class="review-answers"><AnswerOption v-for="key in ['A', 'B', 'C', 'D']" :key="key" :answer="key as 'A' | 'B' | 'C' | 'D'" :name="`review-${reviewIndex}`" :text="currentWrong.options[key as 'A' | 'B' | 'C' | 'D'] ?? ''" :selected="currentWrong.selected === key" :state="currentWrong.correct === key ? 'correct' : currentWrong.selected === key ? 'wrong' : undefined" disabled @select="() => undefined" /></div>
            <dl v-else class="answer-summary"><div><dt>你的选择</dt><dd>{{ currentWrong.selected ?? '未选择' }}</dd></div><div><dt>正确答案</dt><dd>{{ currentWrong.correct }}</dd></div></dl>
            <section class="explanation"><h3>题目解析</h3><p>{{ currentWrong.explanation }}</p></section>
          </template>
          <section v-else class="complete card"><p class="eyebrow">全对了</p><h2>这次没有错题</h2><p>每一道题都判断正确。可以再选一个难度继续练习。</p><RouterLink to="/levels">选择难度</RouterLink></section>
        </section>
      </section>
      <section v-else class="missing-result card"><h1 class="page-title">结果暂不可查看</h1><p>答题结果只保留在本次浏览器会话中。请重新开始一次练习。</p><RouterLink to="/levels">选择难度</RouterLink></section>
    </div>
  </main>
</template>

<style scoped>
.result-page { min-height: 100vh; background: var(--color-bg); }.content { width: min(1280px, calc(100% - clamp(48px, 8vw, 128px))); margin: 0 auto; }.result-layout { display: grid; grid-template-columns: minmax(260px, 4fr) minmax(0, 8fr); gap: 28px; padding: 48px 0 72px; }.score-panel { align-self: start; padding: 30px; }.score-panel h1 { margin: 0; font-size: clamp(58px, 7vw, 88px); line-height: 1; letter-spacing: -.045em; }.score-detail { margin: 12px 0 26px; color: var(--color-text-muted); }.score-panel dl { margin: 0; border-top: 1px solid var(--color-border); }.score-panel dl div { display: flex; justify-content: space-between; gap: 10px; padding: 12px 0; border-bottom: 1px solid var(--color-border); }.score-panel dt { color: var(--color-text-muted); }.score-panel dd { margin: 0; font-weight: 700; }.retry { display: grid; min-height: 46px; margin-top: 24px; place-items: center; border-radius: var(--radius-button); color: #fff; background: var(--color-action); font-weight: 700; }.review-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; margin-bottom: 18px; }.review-header h2 { max-width: 600px; margin: 0; font-size: 25px; line-height: 1.3; }.review-controls { display: flex; gap: 8px; }.review-controls button { min-height: 38px; border: 1px solid var(--color-border); border-radius: 10px; padding: 0 12px; color: var(--color-text); background: #fff; }.review-controls button:disabled { opacity: .5; }.review-answers { display: grid; gap: 10px; margin-top: 18px; }.answer-summary { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 18px 0 0; }.answer-summary div { padding: 12px; border-radius: 12px; background: var(--color-surface-warm); }.answer-summary dt { color: var(--color-text-muted); font-size: 13px; }.answer-summary dd { margin: 6px 0 0; font-weight: 700; }.explanation { margin-top: 18px; padding: 20px; border-radius: 18px; background: var(--color-surface-accent); }.explanation h3 { margin: 0; font-size: 17px; }.explanation p { margin: 10px 0 0; line-height: 1.65; }.complete, .missing-result { padding: 32px; }.complete h2 { margin: 0; }.complete p, .missing-result p { color: var(--color-text-muted); line-height: 1.65; }.complete a, .missing-result a { color: var(--color-action); font-weight: 700; }.missing-result { max-width: 560px; margin: 52px auto; }
@media (max-width: 1023px) { .result-layout { grid-template-columns: 1fr; }.score-panel { display: grid; grid-template-columns: 1fr auto; gap: 12px; }.score-panel .eyebrow { grid-column: 1 / -1; }.score-panel dl { grid-column: 1 / -1; }.retry { margin: 0; align-self: center; padding: 0 20px; } }
@media (max-width: 767px) { .content { width: min(100% - 32px, 1280px); }.result-layout { padding-top: 30px; }.review-header { display: grid; }.score-panel { display: block; }.retry { margin-top: 24px; } }
</style>
