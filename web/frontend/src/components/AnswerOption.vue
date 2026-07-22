<script setup lang="ts">
import type { AnswerKey } from '@/types';

type RadioDirection = 'previous' | 'next';

defineProps<{
  answer: AnswerKey;
  text: string;
  name: string;
  selected: boolean;
  state?: 'correct' | 'wrong';
  disabled?: boolean;
}>();
const emit = defineEmits<{
  select: [answer: AnswerKey];
  move: [answer: AnswerKey, direction: RadioDirection, event: KeyboardEvent];
}>();

function handleKeydown(event: KeyboardEvent, answer: AnswerKey, disabled?: boolean): void {
  if (disabled) return;
  if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') emit('move', answer, 'previous', event);
  if (event.key === 'ArrowRight' || event.key === 'ArrowDown') emit('move', answer, 'next', event);
}
</script>

<template>
  <label class="answer-option" :class="{ selected, correct: state === 'correct', wrong: state === 'wrong', disabled }">
    <input class="native-radio" :name="name" type="radio" :value="answer" :checked="selected" :disabled="disabled" @change="emit('select', answer)" @keydown="handleKeydown($event, answer, disabled)" />
    <span class="answer-key">{{ answer }}</span>
    <span class="answer-text">{{ text }}</span>
    <span v-if="state === 'correct'" class="state-label">正确答案</span>
    <span v-else-if="state === 'wrong'" class="state-label">你的选择</span>
  </label>
</template>

<style scoped>
.answer-option { position: relative; display: grid; width: 100%; min-height: 64px; grid-template-columns: 34px 1fr auto; align-items: center; gap: 12px; padding: 12px 16px; border: 1px solid var(--color-border); border-radius: 16px; color: var(--color-text); background: var(--color-surface); cursor: pointer; text-align: left; transition: transform 100ms ease-out, border-color 160ms ease-out, background 160ms ease-out; }
.answer-option:hover { border-color: #d7ae85; background: var(--color-surface-warm); }
.answer-option:not(.disabled):active { transform: scale(.98); }
.answer-option:focus-within { outline: 3px solid var(--color-focus); outline-offset: 3px; }
.answer-option.disabled { cursor: default; }
.answer-option.selected { border-color: var(--color-action); background: var(--color-surface-accent); }
.answer-option.correct { border-color: var(--color-success); background: #edf8ef; }
.answer-option.wrong { border-color: var(--color-danger); background: #fff0ee; }
.answer-key { display: grid; width: 30px; height: 30px; place-items: center; border: 1px solid currentColor; border-radius: 50%; color: var(--color-text-muted); font-size: 14px; font-weight: 750; }
.selected .answer-key { color: #fff; background: var(--color-action); border-color: var(--color-action); }
.correct .answer-key { color: #fff; background: var(--color-success); border-color: var(--color-success); }
.wrong .answer-key { color: #fff; background: var(--color-danger); border-color: var(--color-danger); }
.answer-text { line-height: 1.5; }
.state-label { color: var(--color-text-muted); font-size: 13px; white-space: nowrap; }
.native-radio { position: absolute; width: 1px; height: 1px; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; }
@media (prefers-reduced-motion: reduce) { .answer-option:active { transform: none; } }
</style>
