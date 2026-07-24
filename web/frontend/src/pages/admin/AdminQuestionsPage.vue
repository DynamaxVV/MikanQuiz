<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage, ElMessageBox, ElPagination, ElTable, ElTableColumn } from 'element-plus';
import { api } from '@/api/client';
import AdminShell from '@/components/AdminShell.vue';
import ErrorPanel from '@/components/ErrorPanel.vue';
import type { Question } from '@/types';

const router = useRouter();
const questions = ref<Question[]>([]);
const page = ref(1);
const total = ref(0);
const difficulties = ref([1, 2, 3]);
const loading = ref(false);
const error = ref('');
const importFileRef = ref<HTMLInputElement | null>(null);

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
    const result = await api.listQuestions(page.value, undefined, difficulties.value);
    questions.value = result.items;
    total.value = result.total;
  } catch (caught) { error.value = caught instanceof Error ? caught.message : '无法读取题库。'; }
  finally { loading.value = false; }
}

function search(): void { page.value = 1; void load(); }
function toggleDifficulty(star: number): void {
  if (difficulties.value.length === 1 && difficulties.value.includes(star)) return;
  difficulties.value = difficulties.value.includes(star)
    ? difficulties.value.filter((value) => value !== star)
    : [...difficulties.value, star].sort();
  search();
}
function changePage(nextPage: number): void { page.value = nextPage; void load(); }
function goDetail(row: unknown): void {
  const question = row as Question;
  void router.push(`/admin/questions/${encodeURIComponent(question.id)}`);
}

async function remove(row: unknown): Promise<void> {
  const question = row as Question;
  try {
    await ElMessageBox.confirm(`“${question.text.slice(0, 80)}”将被永久删除。`, '删除题目', { confirmButtonText: '删除题目', cancelButtonText: '取消', type: 'warning', confirmButtonClass: 'danger-confirm' });
    await api.deleteQuestion(question.id);
    ElMessage.success('题目已删除');
    if (questions.value.length === 1 && page.value > 1) page.value -= 1;
    await load();
  } catch (caught) {
    if (caught !== 'cancel' && caught !== 'close') ElMessage.error(caught instanceof Error ? caught.message : '删除失败，请重试。');
  }
}

onMounted(load);
</script>

<template>
  <AdminShell v-slot="{ session }">
    <section class="admin-content" aria-labelledby="questions-title">
      <header class="page-header"><div><p class="eyebrow">管理员 · {{ session.username }}</p><h1 id="questions-title" class="page-title">题库</h1><p class="page-description">查看和维护现有题目。</p></div></header>
      <section class="toolbar card"><span>难度</span><div class="difficulty-tags" aria-label="按难度筛选"><button v-for="star in 3" :key="star" type="button" :class="{ selected: difficulties.includes(star) }" :aria-pressed="difficulties.includes(star)" @click="toggleDifficulty(star)">{{ '★'.repeat(star) }}</button></div><div class="toolbar-actions"><button type="button" class="action-btn" @click="exportQuestions">导出题库</button><label class="action-btn"><input ref="importFileRef" accept=".json" type="file" hidden @change="handleImport" />导入题库</label></div></section>
      <ErrorPanel v-if="error" :message="error" @retry="load" />
      <section v-else-if="loading" class="loading card">正在读取题库…</section>
      <section v-else-if="questions.length === 0" class="empty-state card"><strong>还没有题目</strong><RouterLink to="/admin/questions/new">新增第一道题</RouterLink></section>
      <section v-else class="table-card card"><el-table :data="questions" row-key="id" @row-click="goDetail"><el-table-column label="缩略图" width="92"><template #default="scope"><img v-if="scope.row.imageUrl" class="thumbnail" :src="scope.row.imageUrl" alt="" /><span v-else class="no-image">无图</span></template></el-table-column><el-table-column prop="text" label="题干" min-width="260" show-overflow-tooltip /><el-table-column label="难度" width="110"><template #default="scope">{{ '★'.repeat(scope.row.difficulty) }}</template></el-table-column><el-table-column prop="answer" label="正确答案" width="110" /><el-table-column label="操作" width="170" fixed="right"><template #default="scope"><div class="row-actions"><RouterLink :to="`/admin/questions/${encodeURIComponent(scope.row.id)}/edit`" @click.stop>编辑</RouterLink><button type="button" @click.stop="remove(scope.row)">删除</button></div></template></el-table-column></el-table></section>
      <el-pagination v-if="total > 0" class="pagination" background layout="prev, pager, next, total" :current-page="page" :page-size="20" :total="total" @current-change="changePage" />
    </section>
  </AdminShell>
</template>

<style scoped>
.admin-content { width: min(1440px, calc(100% - 64px)); margin: 0 auto; padding: 48px 0 64px; }.page-header { margin-bottom: 28px; }.page-description { margin-bottom: 0; }.toolbar { display: flex; align-items: center; gap: 14px; margin-bottom: 20px; padding: 16px; color: var(--color-text-muted); font-size: 13px; font-weight: 700; }.difficulty-tags { display: flex; flex-wrap: wrap; gap: 8px; }.difficulty-tags button { min-height: 34px; border: 1px solid var(--color-border); border-radius: 999px; padding: 0 12px; color: #b9aa99; background: var(--color-surface-warm); font-size: 14px; letter-spacing: 1px; }.difficulty-tags button.selected { border-color: #ebcfad; color: var(--color-action); background: var(--color-surface-accent); }.toolbar-actions { display: flex; gap: 10px; margin-left: auto; }.action-btn { min-height: 34px; border: 1px solid var(--color-border); border-radius: 999px; padding: 0 14px; color: var(--color-action); background: var(--color-surface-warm); font-size: 13px; font-weight: 700; cursor: pointer; display: inline-flex; align-items: center; white-space: nowrap; }.action-btn:hover { border-color: #ebcfad; background: var(--color-surface-accent); }.loading { padding: 32px; color: var(--color-text-muted); }.table-card { overflow: hidden; }.thumbnail { display: block; width: 54px; height: 40px; object-fit: cover; border-radius: 7px; }.no-image { color: var(--color-text-muted); font-size: 13px; }.row-actions { display: flex; gap: 12px; }.row-actions a { color: var(--color-action); font-weight: 700; }.row-actions button { border: 0; padding: 0; color: var(--color-danger); background: transparent; font-weight: 700; }.pagination { justify-content: flex-end; margin-top: 22px; }
@media (max-width: 1023px) { .admin-content { width: min(100% - 32px, 1440px); padding-top: 28px; }.table-card { overflow-x: auto; }.toolbar { flex-wrap: wrap; }.toolbar label { min-width: 200px; }.toolbar-actions { margin-left: 0; width: 100%; display: flex; gap: 10px; }.toolbar-actions .action-btn { flex: 1; justify-content: center; } }
@media (max-width: 600px) { .page-header { display: grid; }.toolbar { align-items: stretch; flex-direction: column; }.toolbar label, .toolbar label:first-child { flex: 1 0 100%; }.toolbar-actions { margin-left: 0; width: 100%; display: flex; gap: 10px; }.toolbar-actions .action-btn { flex: 1; justify-content: center; }.primary-link { width: 100%; }.pagination { justify-content: center; } }
</style>

<style>
.danger-confirm { background: #b5483f !important; border-color: #b5483f !important; }
</style>
