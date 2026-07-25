<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage, ElMessageBox, ElPagination, ElTable, ElTableColumn } from 'element-plus';
import { api } from '@/api/client';
import AdminShell from '@/components/AdminShell.vue';
import ErrorPanel from '@/components/ErrorPanel.vue';
import type { Question, QuestionStats } from '@/types';

const STORAGE_KEY = 'admin-questions-state';
const COLUMN_SORT_MAP: Record<string, string> = { id: 'id', difficulty: 'difficulty', answer: 'answer', updatedAt: 'updated_at' };

const router = useRouter();
const questions = ref<Question[]>([]);
const page = ref(1);
const total = ref(0);
const difficulties = ref([1, 2, 3]);
const loading = ref(false);
const error = ref('');
const importFileRef = ref<HTMLInputElement | null>(null);
const tableRef = ref<{ sort: (prop: string, order: string) => void } | null>(null);
const stats = ref<QuestionStats | null>(null);
const sortBy = ref('updated_at');

const fontStatsByDifficulty = computed(() => {
  if (!stats.value) return [];
  const grouped = new Map<number, { optionName: string; count: number }[]>();
  for (const f of stats.value.byFont) {
    const arr = grouped.get(f.difficulty) ?? [];
    arr.push({ optionName: f.optionName, count: f.count });
    grouped.set(f.difficulty, arr);
  }
  return [...grouped.entries()].sort((a, b) => a[0] - b[0]).map(([difficulty, fonts]) => ({ difficulty, fonts }));
});
const sortOrder = ref('asc');

const defaultSort = ref<{ prop: string; order: 'ascending' | 'descending' }>({ prop: 'updatedAt', order: 'ascending' });

function saveState(): void {
  try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ page: page.value, sortBy: sortBy.value, sortOrder: sortOrder.value })); } catch { /* quota */ }
}

function restoreState(): boolean {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return false;
    const state = JSON.parse(raw) as { page?: number; sortBy?: string; sortOrder?: string };
    if (state.sortBy) { sortBy.value = state.sortBy; sortOrder.value = state.sortOrder === 'asc' ? 'asc' : 'desc'; }
    if (state.page && state.page > 1) page.value = state.page;
    return true;
  } catch { return false; }
}

async function exportQuestions(): Promise<void> {
  try {
    await api.exportQuestions();
    ElMessage.success('题库已导出');
  } catch (caught) {
    ElMessage.error(caught instanceof Error ? caught.message : '导出失败');
  }
}

async function handleImport(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  try {
    const result = await api.importQuestions(file);
    const parts: string[] = [`导入完成：共 ${result.total} 题`];
    if (result.created) parts.push(`成功 ${result.created} 题`);
    if (result.failed) parts.push(`失败 ${result.failed} 题`);
    if (result.errors.length) parts.push(`\n${result.errors.slice(0, 5).join('\n')}${result.errors.length > 5 ? `\n…及其他 ${result.errors.length - 5} 条错误` : ''}`);
    ElMessage({ message: parts.join('，'), type: result.failed ? 'warning' : 'success', duration: result.failed ? 6000 : 3000 });
    await load();
  } catch (caught) {
    ElMessage.error(caught instanceof Error ? caught.message : '导入失败，请检查 JSON 格式');
  } finally {
    input.value = '';
  }
}

async function load(): Promise<void> {
  loading.value = true;
  error.value = '';
  try {
    const result = await api.listQuestions(page.value, undefined, difficulties.value, sortBy.value, sortOrder.value);
    questions.value = result.items;
    total.value = result.total;
  } catch (caught) { error.value = caught instanceof Error ? caught.message : '无法读取题库。'; }
  finally { loading.value = false; }
}

function handleSortChange({ prop, order }: { prop: string | null; order: 'ascending' | 'descending' | null }): void {
  if (!prop || !order) {
    sortBy.value = 'updated_at';
    sortOrder.value = 'asc';
    defaultSort.value = { prop: 'updatedAt', order: 'ascending' };
  } else {
    sortBy.value = COLUMN_SORT_MAP[prop] ?? prop;
    sortOrder.value = order === 'ascending' ? 'asc' : 'desc';
  }
  page.value = 1;
  saveState();
  void load();
}

function search(): void { page.value = 1; saveState(); void load(); }
function toggleDifficulty(star: number): void {
  if (difficulties.value.length === 1 && difficulties.value.includes(star)) return;
  difficulties.value = difficulties.value.includes(star)
    ? difficulties.value.filter((value) => value !== star)
    : [...difficulties.value, star].sort();
  search();
}
function changePage(nextPage: number): void { page.value = nextPage; saveState(); void load(); }
function goDetail(row: unknown): void {
  const question = row as Question;
  const ids = questions.value.map((q) => q.id);
  saveState();
  void router.push(`/admin/questions/${encodeURIComponent(question.id)}?ids=${ids.join(',')}`);
}

async function remove(row: unknown): Promise<void> {
  const question = row as Question;
  try {
    await ElMessageBox.confirm(`"${question.text.slice(0, 80)}"将被永久删除。`, '删除题目', { confirmButtonText: '删除题目', cancelButtonText: '取消', type: 'warning', confirmButtonClass: 'danger-confirm' });
    await api.deleteQuestion(question.id);
    ElMessage.success('题目已删除');
    if (questions.value.length === 1 && page.value > 1) page.value -= 1;
    await load();
  } catch (caught) {
    if (caught !== 'cancel' && caught !== 'close') ElMessage.error(caught instanceof Error ? caught.message : '删除失败，请重试。');
  }
}

async function loadStats(): Promise<void> {
  try { stats.value = await api.getStatistics(); } catch { /* silent */ }
}

function formatDateTime(iso: string | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  const hh = String(d.getHours()).padStart(2, '0');
  const mi = String(d.getMinutes()).padStart(2, '0');
  return `${d.getFullYear()}-${mm}-${dd} ${hh}:${mi}`;
}

onMounted(async () => {
  const restored = restoreState();
  await Promise.all([load(), loadStats()]);
  if (restored && tableRef.value) {
    const prop = Object.entries(COLUMN_SORT_MAP).find(([, v]) => v === sortBy.value)?.[0] ?? '';
    const order = sortOrder.value === 'asc' ? 'ascending' : 'descending';
    await nextTick();
    tableRef.value.sort(prop, order);
  }
});
</script>

<template>
  <AdminShell v-slot="{ session }">
    <section class="admin-content" aria-labelledby="questions-title">
      <header class="page-header"><div><p class="eyebrow">管理员 · {{ session.username }}</p><h1 id="questions-title" class="page-title">题库</h1><p class="page-description">查看和维护现有题目。</p></div></header>
      <section class="toolbar card"><span>难度</span><div class="difficulty-tags" aria-label="按难度筛选"><button v-for="star in 3" :key="star" type="button" :class="{ selected: difficulties.includes(star) }" :aria-pressed="difficulties.includes(star)" @click="toggleDifficulty(star)">{{ '★'.repeat(star) }}</button></div><span class="toolbar-actions"><input ref="importFileRef" accept=".json" type="file" hidden @change="handleImport" /><button type="button" class="action-link" @click="exportQuestions">导出</button><span class="action-sep">·</span><button type="button" class="action-link" @click="importFileRef?.click()">导入</button></span></section>
      <ErrorPanel v-if="error" :message="error" @retry="load" />
      <section v-else-if="loading" class="loading card">正在读取题库…</section>
      <section v-else-if="questions.length === 0" class="empty-state card"><strong>还没有题目</strong><RouterLink to="/admin/questions/new">新增第一道题</RouterLink></section>
      <section v-else class="table-card card"><el-table ref="tableRef" :data="questions" row-key="id" :default-sort="defaultSort" @row-click="goDetail" @sort-change="handleSortChange"><el-table-column prop="id" label="ID" width="70" sortable="custom" /><el-table-column label="缩略图" width="92"><template #default="scope"><img v-if="scope.row.imageUrl" class="thumbnail" :src="scope.row.imageUrl" alt="" /><span v-else class="no-image">无图</span></template></el-table-column><el-table-column prop="text" label="题干" min-width="260" show-overflow-tooltip /><el-table-column label="难度" width="110" sortable="custom" prop="difficulty"><template #default="scope">{{ '★'.repeat(scope.row.difficulty) }}</template></el-table-column><el-table-column prop="answer" label="正确答案" width="110" sortable="custom" /><el-table-column prop="updatedAt" label="更改时间" width="160" sortable="custom"><template #default="scope">{{ formatDateTime(scope.row.updatedAt) }}</template></el-table-column><el-table-column label="操作" width="170" fixed="right"><template #default="scope"><div class="row-actions"><RouterLink :to="`/admin/questions/${encodeURIComponent(scope.row.id)}/edit`" @click.stop>编辑</RouterLink><button type="button" @click.stop="remove(scope.row)">删除</button></div></template></el-table-column></el-table></section>
      <el-pagination v-if="total > 0" class="pagination" background layout="prev, pager, next, total" :current-page="page" :page-size="20" :total="total" @current-change="changePage" />
      <section v-if="stats" class="stats-card card">
        <h2 class="stats-title">统计</h2>
        <div class="stats-body">
          <div class="stats-section">
            <h3 class="stats-subtitle">按难度</h3>
            <div class="difficulty-stats">
              <div v-for="d in stats.byDifficulty" :key="d.difficulty" class="stat-item">
                <span class="stat-label">{{ '★'.repeat(d.difficulty) }}</span>
                <span class="stat-value">{{ d.count }}</span>
              </div>
            </div>
          </div>
          <div class="stats-section">
            <h3 class="stats-subtitle">按正确字体</h3>
            <div v-for="group in fontStatsByDifficulty" :key="group.difficulty" class="font-diff-group">
              <div class="font-diff-label">{{ '★'.repeat(group.difficulty) }}</div>
              <div class="font-cards">
                <div v-for="f in group.fonts" :key="f.optionName" class="font-stat-card">
                  <span class="font-stat-name">{{ f.optionName }}</span>
                  <span class="font-stat-count">{{ f.count }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </section>
  </AdminShell>
</template>

<style scoped>
.admin-content { width: min(1440px, calc(100% - 64px)); margin: 0 auto; padding: 48px 0 64px; }.page-header { margin-bottom: 28px; }.page-description { margin-bottom: 0; }.toolbar { display: flex; align-items: center; gap: 14px; margin-bottom: 20px; padding: 16px; color: var(--color-text-muted); font-size: 13px; font-weight: 700; }.difficulty-tags { display: flex; flex-wrap: wrap; gap: 8px; }.difficulty-tags button { min-height: 34px; border: 1px solid var(--color-border); border-radius: 999px; padding: 0 12px; color: #b9aa99; background: var(--color-surface-warm); font-size: 14px; letter-spacing: 1px; }.difficulty-tags button.selected { border-color: #ebcfad; color: var(--color-action); background: var(--color-surface-accent); }.toolbar-actions { margin-left: auto; display: flex; align-items: center; gap: 6px; }.action-link { border: 0; padding: 0; background: transparent; color: var(--color-text-muted); font: inherit; font-size: 12px; cursor: pointer; }.action-link:hover { color: var(--color-action); }.action-sep { color: var(--color-border); font-size: 12px; }.loading { padding: 32px; color: var(--color-text-muted); }.table-card { overflow: hidden; }.thumbnail { display: block; width: 54px; height: 40px; object-fit: cover; border-radius: 7px; }.no-image { color: var(--color-text-muted); font-size: 13px; }.row-actions { display: flex; gap: 12px; }.row-actions a { color: var(--color-action); font-weight: 700; }.row-actions button { border: 0; padding: 0; color: var(--color-danger); background: transparent; font-weight: 700; }.pagination { justify-content: flex-end; margin-top: 22px; }.stats-card { margin-top: 20px; padding: 24px; }.stats-title { margin: 0 0 20px; font-size: 18px; }.stats-body { display: grid; gap: 24px; }.stats-subtitle { margin: 0 0 12px; font-size: 14px; color: var(--color-text-muted); }.difficulty-stats { display: flex; gap: 24px; }.stat-item { display: flex; flex-direction: column; align-items: center; gap: 4px; min-width: 80px; padding: 12px 16px; border-radius: 10px; background: var(--color-surface-warm); }.stat-label { color: var(--color-action); font-size: 16px; letter-spacing: 2px; }.stat-value { font-size: 22px; font-weight: 700; }.font-diff-group { margin-bottom: 16px; }.font-diff-group:last-child { margin-bottom: 0; }.font-diff-label { margin-bottom: 8px; font-size: 14px; color: var(--color-action); letter-spacing: 2px; }.font-cards { display: flex; flex-wrap: wrap; gap: 10px; }.font-stat-card { display: flex; flex-direction: column; align-items: center; gap: 2px; min-width: 72px; padding: 10px 14px; border-radius: 10px; background: var(--color-surface-warm); }.font-stat-name { font-size: 13px; color: var(--color-text-muted); }.font-stat-count { font-size: 20px; font-weight: 700; }
@media (max-width: 1023px) { .admin-content { width: min(100% - 32px, 1440px); padding-top: 28px; }.table-card { overflow-x: auto; }.toolbar { flex-wrap: wrap; }.toolbar label { min-width: 200px; } }
@media (max-width: 600px) { .page-header { display: grid; }.toolbar { align-items: stretch; flex-direction: column; }.toolbar label, .toolbar label:first-child { flex: 1 0 100%; }.primary-link { width: 100%; }.pagination { justify-content: center; } }
</style>

<style>
.danger-confirm { background: #b5483f !important; border-color: #b5483f !important; }
</style>
