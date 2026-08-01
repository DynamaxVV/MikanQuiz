<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import { api } from '@/api/client';
import AdminShell from '@/components/AdminShell.vue';
import ErrorPanel from '@/components/ErrorPanel.vue';
import QuestionMedia from '@/components/QuestionMedia.vue';
import type { Question, QuestionNavigation } from '@/types';

const route = useRoute();
const router = useRouter();
const question = ref<Question | null>(null);
const navigation = ref<QuestionNavigation | null>(null);
const error = ref('');
const loading = ref(true);
const currentId = computed(() => String(route.params.id));

function difficulties(): number[] {
  const raw = route.query.difficulty;
  const values = Array.isArray(raw) ? raw : raw ? [raw] : [];
  return values.map(Number).filter((value) => value >= 1 && value <= 3);
}
function contextQuery(): Record<string, string | string[]> {
  const values: Record<string, string | string[]> = {};
  for (const [key, value] of Object.entries(route.query)) {
    if (typeof value === 'string') values[key] = value;
    if (Array.isArray(value)) values[key] = value.filter((item): item is string => typeof item === 'string');
  }
  return values;
}
function context(): [string | undefined, number[], string | undefined, string | undefined, string | undefined] {
  return [typeof route.query.query === 'string' ? route.query.query : undefined, difficulties(), typeof route.query.correct_option_id === 'string' ? route.query.correct_option_id : undefined, typeof route.query.sort_by === 'string' ? route.query.sort_by : undefined, typeof route.query.sort_order === 'string' ? route.query.sort_order : undefined];
}

async function load(): Promise<void> {
  loading.value = true;
  error.value = '';
  try {
    const [query, difficulty, correctOptionId, sortBy, sortOrder] = context();
    const [loadedQuestion, loadedNavigation] = await Promise.all([
      api.getQuestion(currentId.value), api.getQuestionNavigation(currentId.value, query, difficulty, correctOptionId, sortBy, sortOrder),
    ]);
    question.value = loadedQuestion;
    navigation.value = loadedNavigation;
  } catch (caught) { error.value = caught instanceof Error ? caught.message : '题目加载失败。'; }
  finally { loading.value = false; }
}
function goQuestion(id: string | undefined): void { if (id) void router.push({ path: `/admin/questions/${encodeURIComponent(id)}`, query: contextQuery() }); }
function backToList(): void { void router.push({ path: '/admin/questions', query: contextQuery() }); }
async function remove(): Promise<void> {
  if (!question.value) return;
  try {
    await ElMessageBox.confirm(`“${question.value.text.slice(0, 80)}”将被永久删除。`, '删除题目', { confirmButtonText: '删除题目', cancelButtonText: '取消', type: 'warning', confirmButtonClass: 'danger-confirm' });
    await api.deleteQuestion(question.value.id); ElMessage.success('题目已删除'); backToList();
  } catch (caught) { if (caught !== 'cancel' && caught !== 'close') ElMessage.error(caught instanceof Error ? caught.message : '删除失败。'); }
}
watch(currentId, () => { void load(); });
onMounted(() => { void load(); });
</script>

<template><AdminShell><section class="admin-content"><div class="top-bar"><button type="button" class="back-link" @click="backToList">← 返回题库</button><nav v-if="navigation" class="nav-bar"><button :disabled="!navigation.previousId" @click="goQuestion(navigation.previousId)">‹ 上一题</button><span>{{ navigation.position }} / {{ navigation.total }}</span><button :disabled="!navigation.nextId" @click="goQuestion(navigation.nextId)">下一题 ›</button></nav></div><div v-if="loading" class="loading card">正在读取题目…</div><ErrorPanel v-else-if="error" :message="error" @retry="load" /><article v-else-if="question" class="detail"><header><div><p class="eyebrow">难度 {{ '★'.repeat(question.difficulty) }}</p><h1 class="page-title">{{ question.text }}</h1><p class="updated">ID: {{ question.id }} · 最后更新：{{ question.updatedAt ? new Date(question.updatedAt).toLocaleString('zh-CN') : '—' }}</p></div><div class="actions"><RouterLink :to="`/admin/questions/${encodeURIComponent(question.id)}/edit`">编辑题目</RouterLink><button type="button" @click="remove">删除题目</button></div></header><div class="detail-grid"><QuestionMedia :image-url="question.imageUrl" :text="question.text" /><section class="question-data card"><h2>正确字体</h2><ol><li class="answer"><strong>{{ question.correctGroup?.name }}</strong><span>{{ question.correctOption?.name }}</span><em>正确答案</em></li></ol><h2>题目解析</h2><p>{{ question.explanation }}</p></section></div></article></section></AdminShell></template>

<style scoped>
.admin-content{width:min(1440px,calc(100% - 64px));margin:0 auto;padding:48px 0 64px}.top-bar{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:18px}.back-link{border:0;padding:0;color:var(--color-action);background:transparent;font:inherit;font-weight:700;cursor:pointer}.nav-bar{display:flex;align-items:center;gap:10px;color:var(--color-text-muted);font-size:13px}.nav-bar button{border:1px solid var(--color-border);border-radius:8px;padding:4px 12px;background:#fff;color:var(--color-action);font-weight:700;cursor:pointer}.nav-bar button:disabled{opacity:.4;cursor:default}.loading{padding:32px}.detail>header{display:flex;justify-content:space-between;gap:20px;margin-bottom:26px}.updated{color:var(--color-text-muted)}.actions{display:flex;align-items:flex-start;gap:10px}.actions a,.actions button{display:grid;min-height:42px;place-items:center;border:1px solid var(--color-border);border-radius:10px;padding:0 14px;font-weight:700}.actions a{color:#fff;background:var(--color-action);border-color:var(--color-action)}.actions button{color:var(--color-danger);background:#fff}.detail-grid{display:grid;grid-template-columns:minmax(0,7fr) minmax(320px,5fr);gap:24px}.question-data{padding:24px}.question-data h2{margin:0 0 16px;font-size:18px}.question-data h2+p{line-height:1.65}.question-data ol{display:grid;gap:8px;padding:0;list-style:none}.question-data li{display:grid;grid-template-columns:1fr auto;gap:10px;align-items:center;padding:11px;border-radius:10px;background:#edf8ef}.question-data em{font-size:12px;font-style:normal;font-weight:700}@media(max-width:1023px){.admin-content{width:min(100% - 32px,1440px);padding-top:28px}.detail-grid{grid-template-columns:1fr}.top-bar{flex-wrap:wrap}}
</style>
