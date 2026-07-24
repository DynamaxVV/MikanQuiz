<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import { api } from '@/api/client';
import AdminShell from '@/components/AdminShell.vue';
import ErrorPanel from '@/components/ErrorPanel.vue';
import QuestionMedia from '@/components/QuestionMedia.vue';
import type { Question } from '@/types';

const route = useRoute();
const router = useRouter();
const question = ref<Question | null>(null);
const error = ref('');
const loading = ref(true);

const ids = ref<string[]>([]);
const currentIndex = computed(() => ids.value.indexOf(String(route.params.id)));
const hasIds = computed(() => ids.value.length > 1);
const hasPrev = computed(() => currentIndex.value > 0);
const hasNext = computed(() => currentIndex.value >= 0 && currentIndex.value < ids.value.length - 1);

async function load(): Promise<void> {
  loading.value = true;
  error.value = '';
  try {
    question.value = await api.getQuestion(String(route.params.id));
    ids.value = history.state?.ids ?? [];
  } catch (caught) { error.value = caught instanceof Error ? caught.message : '题目加载失败。'; }
  finally { loading.value = false; }
}

function goPrev(): void {
  if (!hasPrev.value) return;
  const id = ids.value[currentIndex.value - 1];
  void router.push({ path: `/admin/questions/${encodeURIComponent(id)}`, state: { ids: ids.value } });
}

function goNext(): void {
  if (!hasNext.value) return;
  const id = ids.value[currentIndex.value + 1];
  void router.push({ path: `/admin/questions/${encodeURIComponent(id)}`, state: { ids: ids.value } });
}

async function remove(): Promise<void> {
  if (!question.value) return;
  try {
    await ElMessageBox.confirm(`“${question.value.text.slice(0, 80)}”将被永久删除。`, '删除题目', { confirmButtonText: '删除题目', cancelButtonText: '取消', type: 'warning', confirmButtonClass: 'danger-confirm' });
    await api.deleteQuestion(question.value.id);
    ElMessage.success('题目已删除');
    await router.push('/admin/questions');
  } catch (caught) { if (caught !== 'cancel' && caught !== 'close') ElMessage.error(caught instanceof Error ? caught.message : '删除失败。'); }
}

onMounted(load);
</script>

<template><AdminShell><section class="admin-content"><RouterLink class="back-link" to="/admin/questions">← 返回题库</RouterLink><nav v-if="hasIds" class="nav-bar"><button :disabled="!hasPrev" @click="goPrev">‹ 上一题</button><span class="nav-index">{{ currentIndex + 1 }} / {{ ids.length }}</span><button :disabled="!hasNext" @click="goNext">下一题 ›</button></nav><div v-if="loading" class="loading card">正在读取题目…</div><ErrorPanel v-else-if="error" :message="error" @retry="load" /><article v-else-if="question" class="detail" aria-labelledby="question-title"><header><div><p class="eyebrow">{{ '★'.repeat(question.difficulty) }} 难度</p><h1 id="question-title" class="page-title">{{ question.text }}</h1><p class="updated">最后更新：{{ question.updatedAt ? new Date(question.updatedAt).toLocaleString('zh-CN') : '—' }}</p></div><div class="actions"><RouterLink :to="`/admin/questions/${encodeURIComponent(question.id)}/edit`">编辑题目</RouterLink><button type="button" @click="remove">删除题目</button></div></header><div class="detail-grid"><QuestionMedia :image-url="question.imageUrl" :text="question.text" /><section class="question-data card"><h2>正确字体</h2><ol><li class="answer"><strong>{{ question.correctGroup?.name }}</strong><span>{{ question.correctOption?.name }}</span><em>正确答案</em></li></ol><h2>题目解析</h2><p>{{ question.explanation }}</p></section></div></article></section></AdminShell></template>

<style scoped>
.admin-content { width: min(1440px, calc(100% - 64px)); margin: 0 auto; padding: 48px 0 64px; }.back-link { display: inline-block; margin-bottom: 12px; color: var(--color-action); font-weight: 700; }.nav-bar { display: flex; align-items: center; gap: 12px; margin-bottom: 18px; }.nav-bar button { border: 1px solid var(--color-border); border-radius: 8px; padding: 4px 12px; background: #fff; color: var(--color-action); font-size: 13px; font-weight: 700; cursor: pointer; }.nav-bar button:disabled { opacity: .4; cursor: default; }.nav-bar button:not(:disabled):hover { background: var(--color-surface-accent); }.nav-index { color: var(--color-text-muted); font-size: 13px; }.loading { padding: 32px; color: var(--color-text-muted); }.detail > header { display: flex; justify-content: space-between; gap: 20px; margin-bottom: 26px; }.updated { color: var(--color-text-muted); }.actions { display: flex; align-items: flex-start; gap: 10px; }.actions a, .actions button { display: grid; min-height: 42px; place-items: center; border: 1px solid var(--color-border); border-radius: 10px; padding: 0 14px; font-weight: 700; }.actions a { color: #fff; background: var(--color-action); border-color: var(--color-action); }.actions button { color: var(--color-danger); background: #fff; }.detail-grid { display: grid; grid-template-columns: minmax(0, 7fr) minmax(320px, 5fr); gap: 24px; }.question-data { padding: 24px; }.question-data h2 { margin: 0 0 16px; font-size: 18px; }.question-data h2 + p { line-height: 1.65; }.question-data ol { display: grid; gap: 8px; padding: 0; list-style: none; }.question-data li { display: grid; grid-template-columns: 28px 1fr auto; gap: 10px; align-items: center; padding: 11px; border-radius: 10px; background: var(--color-surface-warm); }.question-data li.answer { color: #21602f; background: #edf8ef; }.question-data em { font-size: 12px; font-style: normal; font-weight: 700; }
@media (max-width: 1023px) { .admin-content { width: min(100% - 32px, 1440px); padding-top: 28px; }.detail-grid { grid-template-columns: 1fr; } }.actions { flex-wrap: wrap; }
</style>
