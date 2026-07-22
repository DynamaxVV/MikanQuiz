<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { ElDialog, ElPagination, ElTable, ElTableColumn } from 'element-plus';
import { api } from '@/api/client';
import AdminShell from '@/components/AdminShell.vue';
import ErrorPanel from '@/components/ErrorPanel.vue';
import QuestionMedia from '@/components/QuestionMedia.vue';
import type { DifficultyMode, SubmissionDetail, SubmissionSummary } from '@/types';

const items = ref<SubmissionSummary[]>([]);
const page = ref(1);
const total = ref(0);
const displayName = ref('');
const loading = ref(false);
const error = ref('');
const detail = ref<SubmissionDetail | null>(null);
const detailLoading = ref(false);
const detailError = ref('');
const dialogOpen = ref(false);
const selectedSubmission = ref<SubmissionSummary | null>(null);
const modeLabels: Record<DifficultyMode, string> = { beginner: '新手级', proficient: '熟练级', challenge: '挑战级' };

async function load(): Promise<void> {
  loading.value = true;
  error.value = '';
  try {
    const result = await api.listSubmissions(page.value, displayName.value.trim() || undefined);
    items.value = result.items;
    total.value = result.total;
  } catch (caught) { error.value = caught instanceof Error ? caught.message : '提交记录加载失败。'; }
  finally { loading.value = false; }
}

function search(): void { page.value = 1; void load(); }
function changePage(nextPage: number): void { page.value = nextPage; void load(); }

async function openDetail(item: SubmissionSummary): Promise<void> {
  selectedSubmission.value = item;
  dialogOpen.value = true;
  detail.value = null;
  detailLoading.value = true;
  detailError.value = '';
  try { detail.value = await api.getSubmission(item.id); }
  catch (caught) { detailError.value = caught instanceof Error ? caught.message : '答题明细加载失败。'; }
  finally { detailLoading.value = false; }
}

onMounted(load);
</script>

<template><AdminShell><section class="admin-content" aria-labelledby="submissions-title"><header><p class="eyebrow">历史记录</p><h1 id="submissions-title" class="page-title">提交记录</h1><p class="page-description">历史提交会永久保留；列表始终通过分页加载。</p></header><section class="toolbar card"><label>按昵称筛选<input v-model="displayName" type="search" maxlength="20" placeholder="输入昵称" @keyup.enter="search" /></label><button type="button" @click="search">搜索</button></section><ErrorPanel v-if="error" :message="error" @retry="load" /><section v-else-if="loading" class="loading card">正在读取提交记录…</section><section v-else-if="items.length === 0" class="empty-state card">暂无提交记录</section><section v-else class="table-card card"><el-table :data="items" row-key="id" @row-click="openDetail"><el-table-column prop="displayName" label="昵称" min-width="140" /><el-table-column label="分数" width="90"><template #default="scope">{{ scope.row.score }} 分</template></el-table-column><el-table-column label="答对 / 总题数" width="140"><template #default="scope">{{ scope.row.correctCount }} / {{ scope.row.totalCount }}</template></el-table-column><el-table-column label="难度" width="110"><template #default="scope">{{ modeLabels[scope.row.mode as DifficultyMode] }}</template></el-table-column><el-table-column label="提交时间" min-width="180"><template #default="scope">{{ new Date(scope.row.submittedAt).toLocaleString('zh-CN') }}</template></el-table-column></el-table></section><el-pagination v-if="total" class="pagination" background layout="prev, pager, next, total" :current-page="page" :page-size="20" :total="total" @current-change="changePage" /><el-dialog v-model="dialogOpen" title="答题明细" width="min(760px, calc(100vw - 32px))" destroy-on-close><div v-if="detailLoading">正在读取答题明细…</div><ErrorPanel v-else-if="detailError" :message="detailError" @retry="selectedSubmission && openDetail(selectedSubmission)" /><section v-else-if="detail" class="submission-detail"><p><strong>{{ detail.displayName }}</strong> · {{ detail.score }} 分 · {{ detail.correctCount }} / {{ detail.totalCount }} 题正确</p><article v-for="(answer, index) in detail.answers" :key="index"><h2>第 {{ index + 1 }} 题：{{ answer.questionText }}</h2><QuestionMedia v-if="answer.imageUrl" :image-url="answer.imageUrl" :text="answer.questionText" /><dl><div><dt>你的选择</dt><dd :class="{ wrong: answer.selected !== answer.correct }">{{ answer.selected ?? '未选择' }}</dd></div><div><dt>正确答案</dt><dd class="correct">{{ answer.correct }}</dd></div></dl><p class="explanation"><strong>题目解析：</strong>{{ answer.explanation }}</p></article></section></el-dialog></section></AdminShell></template>

<style scoped>
.admin-content { width: min(1440px, calc(100% - 64px)); margin: 0 auto; padding: 48px 0 64px; }.page-description { margin-bottom: 0; }.toolbar { display: flex; align-items: end; gap: 12px; margin: 28px 0 20px; padding: 16px; }.toolbar label { display: grid; flex: 1; gap: 8px; color: var(--color-text-muted); font-size: 13px; font-weight: 700; }.toolbar input { min-height: 40px; border: 1px solid var(--color-border); border-radius: var(--radius-input); padding: 0 11px; color: var(--color-text); background: var(--color-surface-warm); }.toolbar button { min-height: 40px; border: 1px solid var(--color-border); border-radius: 10px; padding: 0 16px; background: #fff; font-weight: 700; }.loading { padding: 32px; color: var(--color-text-muted); }.table-card { overflow: hidden; }.pagination { justify-content: flex-end; margin-top: 22px; }.submission-detail > p { margin-top: 0; color: var(--color-text-muted); }.submission-detail article { padding: 18px 0; border-top: 1px solid var(--color-border); }.submission-detail h2 { margin: 0 0 14px; font-size: 17px; line-height: 1.5; }.submission-detail dl { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 14px 0; }.submission-detail dl div { padding: 10px; border-radius: 10px; background: var(--color-surface-warm); }.submission-detail dt { color: var(--color-text-muted); font-size: 13px; }.submission-detail dd { margin: 5px 0 0; font-weight: 750; }.submission-detail .wrong { color: var(--color-danger); }.submission-detail .correct { color: var(--color-success); }.explanation { line-height: 1.65; }
@media (max-width: 1023px) { .admin-content { width: min(100% - 32px, 1440px); padding-top: 28px; }.table-card { overflow-x: auto; } }.toolbar { flex-wrap: wrap; }
</style>
