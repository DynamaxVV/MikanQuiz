<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { ElInputNumber, ElMessage } from 'element-plus';
import { api } from '@/api/client';
import AdminShell from '@/components/AdminShell.vue';
import ErrorPanel from '@/components/ErrorPanel.vue';
import type { DifficultyMode, QuizSettings } from '@/types';

const settings = reactive<Pick<QuizSettings, 'questionCount' | 'modes'>>({ questionCount: 10, modes: { beginner: [0, 0, 0, 0, 0], proficient: [0, 0, 0, 0, 0], challenge: [0, 0, 0, 0, 0] } });
const ready = ref(false);
const loading = ref(true);
const saving = ref(false);
const error = ref('');
const modeRows: { key: DifficultyMode; title: string; description: string }[] = [
  { key: 'beginner', title: '新手级', description: '从基础字形开始' },
  { key: 'proficient', title: '熟练级', description: '平衡观察与判断' },
  { key: 'challenge', title: '挑战级', description: '挑战容易混淆的字形' },
];

function sum(mode: DifficultyMode): number { return settings.modes[mode].reduce((total, value) => total + Number(value || 0), 0); }
function valid(mode: DifficultyMode): boolean { return sum(mode) > 0; }

async function load(): Promise<void> {
  loading.value = true;
  error.value = '';
  try {
    const current = await api.getAdminSettings();
    settings.questionCount = current.questionCount;
    settings.modes = { beginner: [...current.modes.beginner], proficient: [...current.modes.proficient], challenge: [...current.modes.challenge] };
    ready.value = true;
  } catch (caught) { error.value = caught instanceof Error ? caught.message : '出题策略加载失败。'; }
  finally { loading.value = false; }
}

async function save(): Promise<void> {
  if (!modeRows.every((row) => valid(row.key))) { error.value = '每种难度至少要保留一个大于 0 的权重。'; return; }
  if (settings.questionCount < 1 || settings.questionCount > 50) { error.value = '每次题数必须在 1 到 50 之间。'; return; }
  saving.value = true;
  error.value = '';
  try { await api.saveStrategy({ questionCount: Number(settings.questionCount), modes: settings.modes }); ElMessage.success('出题策略已保存'); }
  catch (caught) { error.value = caught instanceof Error ? caught.message : '策略保存失败。'; }
  finally { saving.value = false; }
}

onMounted(load);
</script>

<template><AdminShell><section class="admin-content" aria-labelledby="strategy-title"><header><p class="eyebrow">题库设置</p><h1 id="strategy-title" class="page-title">出题策略</h1><p class="page-description">设置每次抽题数量，以及三种难度中各星级题目的相对权重。</p></header><div v-if="loading" class="loading card">正在读取出题策略…</div><ErrorPanel v-else-if="error && !ready" :message="error" @retry="load" /><form v-else class="strategy card" @submit.prevent="save"><label class="count-field">每次题数<el-input-number v-model="settings.questionCount" :min="1" :max="50" controls-position="right" /></label><div class="matrix"><div class="matrix-heading"><span>难度</span><span v-for="star in 5" :key="star">{{ star }} 星</span><span>权重合计</span></div><div v-for="row in modeRows" :key="row.key" class="matrix-row"><div><strong>{{ row.title }}</strong><small>{{ row.description }}</small></div><el-input-number v-for="(_, index) in settings.modes[row.key]" :key="index" v-model="settings.modes[row.key][index]" :min="0" :max="100" controls-position="right" /><strong :class="{ invalid: !valid(row.key) }">{{ sum(row.key) }}{{ valid(row.key) ? '' : '（至少为 1）' }}</strong></div></div><p v-if="error" class="status-error" role="alert">{{ error }}</p><button type="submit" :disabled="saving">{{ saving ? '正在保存…' : '保存出题策略' }}</button></form></section></AdminShell></template>

<style scoped>
.admin-content { width: min(1040px, calc(100% - 64px)); margin: 0 auto; padding: 48px 0 64px; }.page-description { max-width: 670px; }.loading, .strategy { margin-top: 28px; padding: 28px; }.strategy { display: grid; gap: 28px; }.count-field { display: grid; width: min(260px, 100%); gap: 8px; font-size: 14px; font-weight: 750; }.matrix { overflow-x: auto; }.matrix-heading, .matrix-row { display: grid; min-width: 770px; grid-template-columns: 1.6fr repeat(5, 100px) 120px; align-items: center; gap: 10px; }.matrix-heading { padding: 0 0 10px; color: var(--color-text-muted); font-size: 13px; font-weight: 700; }.matrix-row { padding: 14px 0; border-top: 1px solid var(--color-border); }.matrix-row > div:first-child { display: grid; gap: 4px; }.matrix-row small { color: var(--color-text-muted); }.invalid { color: var(--color-danger); }.strategy > button { justify-self: start; min-height: 46px; border: 0; border-radius: var(--radius-button); padding: 0 20px; color: #fff; background: var(--color-action); font-weight: 750; }.strategy > button:hover { background: var(--color-action-hover); }.strategy > button:disabled { opacity: .65; }
@media (max-width: 1023px) { .admin-content { width: min(100% - 32px, 1040px); padding-top: 28px; } }
</style>
