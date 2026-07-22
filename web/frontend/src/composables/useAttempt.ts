import { computed, ref } from 'vue';
import { api, ApiError } from '@/api/client';
import type { AnswerKey, DifficultyMode, QuizAttempt, SubmissionResult } from '@/types';

const ATTEMPT_KEY = 'hanzipen-attempt-token';
const ANSWERS_KEY = 'hanzipen-attempt-answers';

function readAnswers(): Record<string, AnswerKey> {
  try {
    return JSON.parse(localStorage.getItem(ANSWERS_KEY) ?? '{}') as Record<string, AnswerKey>;
  } catch {
    return {};
  }
}

function persistAnswers(answers: Record<string, AnswerKey>): void {
  localStorage.setItem(ANSWERS_KEY, JSON.stringify(answers));
}

export function useAttempt() {
  const attempt = ref<QuizAttempt | null>(null);
  const answers = ref<Record<string, AnswerKey>>(readAnswers());
  const error = ref<string>('');
  const loading = ref(false);
  const submitting = ref(false);
  const completed = computed(() => attempt.value?.questions.every((question) => Boolean(answers.value[question.id])) ?? false);

  function clearSavedAttempt(): void {
    localStorage.removeItem(ATTEMPT_KEY);
    localStorage.removeItem(ANSWERS_KEY);
    answers.value = {};
  }

  function selectAnswer(questionId: string, answer: AnswerKey): void {
    answers.value = { ...answers.value, [questionId]: answer };
    persistAnswers(answers.value);
  }

  async function create(mode: DifficultyMode): Promise<QuizAttempt> {
    loading.value = true;
    error.value = '';
    try {
      const nextAttempt = await api.createAttempt(mode);
      if (!nextAttempt.token) throw new ApiError('服务未返回可恢复答题凭据。', 500, 'ATTEMPT_TOKEN_MISSING');
      attempt.value = nextAttempt;
      answers.value = {};
      localStorage.setItem(ATTEMPT_KEY, nextAttempt.token);
      persistAnswers({});
      return nextAttempt;
    } catch (caught) {
      error.value = caught instanceof Error ? caught.message : '开始答题失败，请重试。';
      throw caught;
    } finally {
      loading.value = false;
    }
  }

  async function restore(): Promise<QuizAttempt | null> {
    const token = localStorage.getItem(ATTEMPT_KEY);
    if (!token) return null;
    loading.value = true;
    error.value = '';
    try {
      const savedAttempt = await api.getCurrentAttempt(token);
      if (savedAttempt.submitted) {
        clearSavedAttempt();
        return null;
      }
      attempt.value = savedAttempt;
      return savedAttempt;
    } catch (caught) {
      if (caught instanceof ApiError && [401, 404, 410].includes(caught.status)) clearSavedAttempt();
      else error.value = caught instanceof Error ? caught.message : '恢复答题失败，请重试。';
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function submit(displayName: string): Promise<SubmissionResult> {
    const token = localStorage.getItem(ATTEMPT_KEY);
    if (!attempt.value || !token) throw new ApiError('答题会话已失效，请重新开始。', 410, 'ATTEMPT_EXPIRED');
    submitting.value = true;
    error.value = '';
    try {
      const result = await api.submitAttempt(token, displayName, answers.value);
      if (attempt.value) attempt.value = { ...attempt.value, submitted: true };
      clearSavedAttempt();
      return result;
    } catch (caught) {
      error.value = caught instanceof Error ? caught.message : '提交失败，请重试。';
      throw caught;
    } finally {
      submitting.value = false;
    }
  }

  return { attempt, answers, error, loading, submitting, completed, clearSavedAttempt, create, restore, selectAnswer, submit };
}
