<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage, ElMessageBox, ElPagination, ElTable, ElTableColumn } from 'element-plus';
import { api } from '@/api/client';
import AdminShell from '@/components/AdminShell.vue';
import ErrorPanel from '@/components/ErrorPanel.vue';
import type { OptionGroup, Question, QuestionStats } from '@/types';

const STORAGE_KEY = 'admin-questions-state';
const COLUMN_SORT_MAP: Record<string, string> = { id: 'id', difficulty: 'difficulty', answer: 'answer', updatedAt: 'updated_at' };
const route = useRoute();
const router = useRouter();
const questions = ref<Question[]>([]);
const catalog = ref<OptionGroup[]>([]);
const page = ref(1);
const total = ref(0);
const difficulties = ref([1, 2, 3]);
const correctOptionId = ref('');
const loading = ref(false);
const error = ref('');
const stats = ref<QuestionStats | null>(null);
const sortBy = ref('updated_at');
const sortOrder = ref('asc');
const selectedFontName = computed(() => catalog.value.flatMap((group) => group.options).find((option) => option.id === correctOptionId.value)?.name ?? '');

function queryValues(): Record<string, string | string[]> {
  return {
    page: String(page.value), difficulty: difficulties.value.map(String),
    ...(correctOptionId.value ? { correct_option_id: correctOptionId.value } : {}),
    sort_by: sortBy.value, sort_order: sortOrder.value,
  };
}

function saveState(): void {
  try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(queryValues())); } catch { /* quota */ }
  void router.replace({ query: queryValues() });
}

function applyState(raw: Record<string, unknown>): void {
  const listedDifficulties = Array.isArray(raw.difficulty) ? raw.difficulty : typeof raw.difficulty === 'string' ? [raw.difficulty] : [];
  const parsedDifficulties = listedDifficulties.map(Number).filter((value) => value >= 1 && value <= 3);
  if (parsedDifficulties.length) difficulties.value = [...new Set(parsedDifficulties)].sort();
  const requestedPage = Number(raw.page);
  if (Number.isInteger(requestedPage) && requestedPage > 0) page.value = requestedPage;
  correctOptionId.value = typeof raw.correct_option_id === 'string' ? raw.correct_option_id : '';
  if (typeof raw.sort_by === 'string') sortBy.value = raw.sort_by;
  if (raw.sort_order === 'desc' || raw.sort_order === 'asc') sortOrder.value = raw.sort_order;
}

function restoreState(): void {
  if (Object.keys(route.query).length) { applyState(route.query); return; }
  try { const saved = sessionStorage.getItem(STORAGE_KEY); if (saved) applyState(JSON.parse(saved) as Record<string, unknown>); } catch { /* default state */ }
}

async function load(): Promise<void> {
  loading.value = true;
  error.value = '';
  try {
    const result = await api.listQuestions(page.value, undefined, difficulties.value, correctOptionId.value || undefined, sortBy.value, sortOrder.value);
    questions.value = result.items;
    total.value = result.total;
    if (page.value > 1 && !questions.value.length) { page.value = Math.max(1, Math.ceil(total.value / 20)); saveState(); await load(); }
  } catch (caught) { error.value = caught instanceof Error ? caught.message : '无法读取题库。'; }
  finally { loading.value = false; }
}

function refresh(resetPage = true): void { if (resetPage) page.value = 1; saveState(); void load(); }
function toggleDifficulty(star: number): void {
  if (difficulties.value.length === 1 && difficulties.value.includes(star)) return;
  difficulties.value = difficulties.value.includes(star) ? difficulties.value.filter((value) => value !== star) : [...difficulties.value, star].sort();
  refresh();
}
function setFontFilter(): void { refresh(); }
function clearFilters(): void { difficulties.value = [1, 2, 3]; correctOptionId.value = ''; refresh(); }
function changePage(nextPage: number): void { page.value = nextPage; saveState(); void load(); }
function handleSortChange({ prop, order }: { prop: string | null; order: 'ascending' | 'descending' | null }): void {
  sortBy.value = prop && order ? COLUMN_SORT_MAP[prop] ?? prop : 'updated_at';
  sortOrder.value = order === 'descending' ? 'desc' : 'asc';
  refresh();
}
function goDetail(row: unknown): void { const question = row as Question; saveState(); void router.push({ path: `/admin/questions/${encodeURIComponent(question.id)}`, query: queryValues() }); }
function selectDifficultyStat(difficulty: number): void { difficulties.value = [difficulty]; correctOptionId.value = ''; refresh(); }
function selectFontStat(optionId: string): void { difficulties.value = [1, 2, 3]; correctOptionId.value = optionId; refresh(); }

async function remove(row: unknown): Promise<void> {
  const question = row as Question;
  try {
    await ElMessageBox.confirm(`"${question.text.slice(0, 80)}"将被永久删除。`, '删除题目', { confirmButtonText: '删除题目', cancelButtonText: '取消', type: 'warning', confirmButtonClass: 'danger-confirm' });
    await api.deleteQuestion(question.id); ElMessage.success('题目已删除');
    if (questions.value.length === 1 && page.value > 1) page.value -= 1;
    saveState(); await load();
  } catch (caught) { if (caught !== 'cancel' && caught !== 'close') ElMessage.error(caught instanceof Error ? caught.message : '删除失败，请重试。'); }
}

function formatDateTime(iso: string | undefined): string { return iso ? new Date(iso).toLocaleString('zh-CN') : '—'; }

onMounted(async () => {
  restoreState();
  await Promise.all([
    load(), api.getStatistics().then((value) => { stats.value = value; }),
    api.getOptionGroups().then((value) => { catalog.value = value; }),
  ]);
  saveState();
});
</script>

<template>
  <AdminShell><section class="admin-content" aria-labelledby="questions-title">
    <header class="page-header"><p class="eyebrow">题库管理</p><h1 id="questions-title" class="page-title">题库</h1><p class="page-description">筛选、排序与页码会在查看题目详情后保持不变。</p></header>
    <section class="toolbar card">
      <span>难度</span><div class="difficulty-tags" aria-label="按难度筛选"><button v-for="star in 3" :key="star" type="button" :class="{ selected: difficulties.includes(star) }" :aria-pressed="difficulties.includes(star)" @click="toggleDifficulty(star)">{{ '★'.repeat(star) }}</button></div>
      <label class="font-filter">正确字体<select v-model="correctOptionId" @change="setFontFilter"><option value="">全部字体</option><optgroup v-for="group in catalog" :key="group.id" :label="group.name"><option v-for="option in group.options" :key="option.id" :value="option.id">{{ option.name }}</option></optgroup></select></label>
      <button type="button" class="action-link" :disabled="difficulties.length === 3 && !correctOptionId" @click="clearFilters">清除筛选</button>
    </section>
    <p v-if="selectedFontName" class="filter-summary">当前正确字体：{{ selectedFontName }}</p>
    <ErrorPanel v-if="error" :message="error" @retry="load" />
    <section v-else-if="loading" class="loading card">正在读取题库…</section>
    <section v-else-if="questions.length === 0" class="empty-state card">没有匹配的题目</section>
    <section v-else class="table-card card"><el-table :data="questions" row-key="id" @row-click="goDetail" @sort-change="handleSortChange"><el-table-column prop="id" label="ID" width="70" sortable="custom" /><el-table-column label="缩略图" width="92"><template #default="scope"><img v-if="scope.row.imageUrl" class="thumbnail" :src="scope.row.imageUrl" alt="" /><span v-else>无图</span></template></el-table-column><el-table-column prop="text" label="题干" min-width="260" show-overflow-tooltip /><el-table-column prop="difficulty" label="难度" width="110" sortable="custom"><template #default="scope">{{ '★'.repeat(scope.row.difficulty) }}</template></el-table-column><el-table-column prop="answer" label="正确答案" width="110" sortable="custom" /><el-table-column prop="updatedAt" label="更改时间" width="170" sortable="custom"><template #default="scope">{{ formatDateTime(scope.row.updatedAt) }}</template></el-table-column><el-table-column label="操作" width="170" fixed="right"><template #default="scope"><div class="row-actions"><RouterLink :to="`/admin/questions/${encodeURIComponent(scope.row.id)}/edit`" @click.stop>编辑</RouterLink><button type="button" @click.stop="remove(scope.row)">删除</button></div></template></el-table-column></el-table></section>
    <el-pagination v-if="total > 0" class="pagination" background layout="prev, pager, next, total" :current-page="page" :page-size="20" :total="total" @current-change="changePage" />
    <section v-if="stats" class="stats-card card"><h2>统计</h2><div class="stats-body"><div><h3>按难度</h3><div class="stat-row"><button v-for="item in stats.byDifficulty" :key="item.difficulty" type="button" class="stat-item" :class="{ selected: difficulties.length === 1 && difficulties[0] === item.difficulty && !correctOptionId }" @click="selectDifficultyStat(item.difficulty)"><span>{{ '★'.repeat(item.difficulty) }}</span><strong>{{ item.count }}</strong></button></div></div><div><h3>按正确字体</h3><div class="stat-row"><button v-for="item in stats.byFont" :key="item.optionId" type="button" class="stat-item" :class="{ selected: correctOptionId === item.optionId }" @click="selectFontStat(item.optionId)"><span>{{ item.optionName }}</span><strong>{{ item.count }}</strong></button></div></div></div></section>
  </section></AdminShell>
</template>

<style scoped>
.admin-content{width:min(1440px,calc(100% - 64px));margin:0 auto;padding:48px 0 64px}.page-header{margin-bottom:28px}.page-description,.filter-summary{color:var(--color-text-muted)}.toolbar{display:flex;align-items:center;gap:14px;margin-bottom:10px;padding:16px;color:var(--color-text-muted);font-size:13px;font-weight:700}.difficulty-tags,.stat-row{display:flex;flex-wrap:wrap;gap:8px}.difficulty-tags button,.stat-item{min-height:34px;border:1px solid var(--color-border);border-radius:10px;padding:7px 12px;color:var(--color-action);background:var(--color-surface-warm);font:inherit;cursor:pointer}.difficulty-tags button.selected,.stat-item.selected{border-color:#ebcfad;background:var(--color-surface-accent)}.font-filter{display:flex;align-items:center;gap:8px}.font-filter select{min-height:34px;border:1px solid var(--color-border);border-radius:8px;background:#fff;padding:0 8px}.action-link{margin-left:auto;border:0;background:transparent;color:var(--color-action);font:inherit;cursor:pointer}.action-link:disabled{color:var(--color-text-muted);cursor:default}.loading,.empty-state{padding:32px}.table-card{overflow:hidden}.thumbnail{display:block;width:54px;height:40px;object-fit:cover;border-radius:7px}.row-actions{display:flex;gap:12px}.row-actions a{color:var(--color-action);font-weight:700}.row-actions button{border:0;padding:0;color:var(--color-danger);background:transparent;font:inherit}.pagination{justify-content:flex-end;margin-top:22px}.stats-card{margin-top:20px;padding:24px}.stats-body{display:grid;gap:20px}.stats-body h3{font-size:14px;color:var(--color-text-muted)}.stat-item{display:flex;flex-direction:column;align-items:center;gap:3px;min-width:72px}.stat-item:hover{background:var(--color-surface-accent)}@media(max-width:760px){.admin-content{width:min(100% - 32px,1440px);padding-top:28px}.toolbar{align-items:stretch;flex-direction:column}.action-link{margin-left:0;text-align:left}.table-card{overflow-x:auto}}
</style>
