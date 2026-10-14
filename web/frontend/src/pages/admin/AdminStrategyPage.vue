<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { ElInputNumber, ElMessage } from 'element-plus';
import { api } from '@/api/client';
import { useUnsavedGuard } from '@/composables/useUnsavedGuard';
import AdminShell from '@/components/AdminShell.vue';
import ErrorPanel from '@/components/ErrorPanel.vue';
import type { DifficultyMode, QuizSettings } from '@/types';
const settings = reactive<Pick<QuizSettings, 'questionCount' | 'modes'>>({ questionCount: 10, modes: { beginner: [0, 0, 0], proficient: [0, 0, 0], challenge: [0, 0, 0] } });
const { markSaved } = useUnsavedGuard(() => ({ questionCount: settings.questionCount, modes: { beginner: [...settings.modes.beginner], proficient: [...settings.modes.proficient], challenge: [...settings.modes.challenge] } }));
const ready = ref(false); const loading = ref(true); const saving = ref(false); const error = ref('');
const modeRows: { key: DifficultyMode; title: string; description: string }[] = [{ key: 'beginner', title: '新手级', description: '从基础字形开始' }, { key: 'proficient', title: '熟练级', description: '平衡观察与判断' }, { key: 'challenge', title: '挑战级', description: '挑战容易混淆的字形' }];
function sum(mode: DifficultyMode): number { return settings.modes[mode].reduce((total, value) => total + Number(value || 0), 0); }
function valid(mode: DifficultyMode): boolean { return sum(mode) > 0; }
async function load(): Promise<void> { loading.value = true; error.value = ''; try { const current = await api.getAdminSettings(); settings.questionCount = current.questionCount; settings.modes = { beginner: [...current.modes.beginner], proficient: [...current.modes.proficient], challenge: [...current.modes.challenge] }; ready.value = true; markSaved(); } catch (caught) { error.value = caught instanceof Error ? caught.message : '出题策略加载失败。'; } finally { loading.value = false; } }
async function save(): Promise<void> { if (!modeRows.every((row) => valid(row.key))) { error.value = '每种难度至少要保留一个大于 0 的比例。'; return; } saving.value = true; error.value = ''; try { await api.saveStrategy({ questionCount: Number(settings.questionCount), modes: settings.modes }); ElMessage.success('出题策略已保存'); markSaved(); } catch (caught) { error.value = caught instanceof Error ? caught.message : '策略保存失败。'; } finally { saving.value = false; } }
onMounted(load);
</script>
<template>
  <AdminShell>
    <section class="admin-content">
      <header class="page-header">
        <div class="page-heading">
          <p class="eyebrow">题库设置</p>
          <h1 class="page-title">出题策略</h1>
          <p class="page-description">决定每次练习抽取多少题，以及不同星级题目的出现权重。</p>
        </div>
        <div class="strategy-badge" aria-label="策略范围">
          <span class="badge-dot" aria-hidden="true"></span>
          <span>当前策略</span>
          <strong>{{ settings.questionCount }} 题 / 次</strong>
        </div>
      </header>

      <div v-if="loading" class="loading card">正在读取出题策略…</div>
      <ErrorPanel v-else-if="error && !ready" :message="error" @retry="load" />

      <form v-else class="strategy" @submit.prevent="save">
        <section class="card count-card">
          <div class="count-copy">
            <p class="eyebrow">01 · 每次练习</p>
            <h2>先决定练习长度</h2>
            <p>每次开始练习时，会按照下面的权重抽取题目。</p>
          </div>
          <div class="count-control">
            <span class="control-label">题目数量</span>
            <label class="count-input">
              <el-input-number v-model="settings.questionCount" :min="1" :max="50" controls-position="right" aria-label="每次练习题目数量" />
              <span>题</span>
            </label>
          </div>
        </section>

        <section class="card strategy-card">
          <header class="section-header">
            <div>
              <p class="eyebrow">02 · 星级权重</p>
              <h2>三档难度怎么抽</h2>
            </div>
            <p class="section-note">权重越高，抽到该星级的机会越大</p>
          </header>

          <div class="mode-list">
            <article v-for="row in modeRows" :key="row.key" class="mode-card" :class="`mode-${row.key}`">
              <div class="mode-meta">
                <div class="mode-mark" aria-hidden="true">
                  <span>{{ row.key === 'beginner' ? '1' : row.key === 'proficient' ? '2' : '3' }}</span>★
                </div>
                <div>
                  <h3>{{ row.title }}</h3>
                  <p>{{ row.description }}</p>
                </div>
              </div>

              <div class="weight-grid">
                <label v-for="(_, index) in settings.modes[row.key]" :key="index" class="weight-field">
                  <span>{{ index + 1 }}★</span>
                  <el-input-number v-model="settings.modes[row.key][index]" :min="0" :max="100" controls-position="right" :aria-label="`${row.title}${index + 1}星权重`" />
                </label>
              </div>

              <div class="total-box" :class="{ invalid: !valid(row.key) }">
                <span>合计</span>
                <strong>{{ sum(row.key) }}</strong>
                <small><i aria-hidden="true">{{ valid(row.key) ? '✓' : '!' }}</i>{{ valid(row.key) ? '可用于抽题' : '至少配置一项' }}</small>
              </div>
            </article>
          </div>
        </section>

        <p v-if="error" class="status-error">{{ error }}</p>
        <footer class="save-bar">
          <div>
            <strong>准备好更新策略了吗？</strong>
            <p>保存后，下一次练习立即使用新设置。</p>
          </div>
          <button :disabled="saving" type="submit">{{ saving ? '正在保存…' : '保存出题策略' }}<span aria-hidden="true">→</span></button>
        </footer>
      </form>
    </section>
  </AdminShell>
</template>

<style scoped>
.admin-content { width: min(1180px, calc(100% - 64px)); margin: 0 auto; padding: 48px 0 64px; }
.page-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 32px; margin-bottom: 32px; }
.page-description { max-width: 680px; margin: 10px 0 0; }
.strategy-badge { display: flex; align-items: center; gap: 8px; flex: 0 0 auto; min-height: 44px; border: 1px solid #edcfac; border-radius: 14px; padding: 0 14px; color: var(--color-text-muted); background: var(--color-surface-accent); font-size: 13px; }
.strategy-badge strong { margin-left: 2px; color: var(--color-action); font-size: 14px; }
.badge-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--color-success); box-shadow: 0 0 0 4px rgba(57, 134, 74, .12); }
.loading { padding: 24px; }
.strategy { display: grid; gap: 20px; }
.count-card { display: grid; grid-template-columns: 1fr auto; align-items: center; gap: 32px; padding: 26px 28px; }
.count-copy h2, .strategy-card h2 { margin: 4px 0 0; color: var(--color-text); font-size: 22px; letter-spacing: -.02em; }
.count-copy p:last-child { margin: 8px 0 0; color: var(--color-text-muted); font-size: 14px; }
.count-control { display: grid; justify-items: end; gap: 8px; }
.control-label { color: var(--color-text-muted); font-size: 13px; font-weight: 700; }
.count-input { display: flex; align-items: center; gap: 10px; color: var(--color-action); font-weight: 750; }
.count-input :deep(.el-input-number) { width: 150px; }
.strategy-card { padding: 28px; }
.section-header { display: flex; align-items: end; justify-content: space-between; gap: 24px; }
.section-note { margin: 0 0 2px; color: var(--color-text-muted); font-size: 13px; }
.mode-list { display: grid; gap: 12px; margin-top: 26px; }
.mode-card { display: grid; grid-template-columns: minmax(220px, 1.1fr) minmax(360px, 2fr) minmax(0, 126px); align-items: center; gap: 24px; min-width: 0; border: 1px solid var(--color-border); border-radius: 18px; padding: 18px 20px; background: var(--color-surface-warm); }
.mode-card:hover { border-color: #ebc99f; box-shadow: 0 8px 20px rgba(116, 72, 20, .05); }
.mode-meta { display: flex; min-width: 0; align-items: center; gap: 14px; }
.mode-mark { display: grid; width: 46px; height: 46px; flex: 0 0 46px; place-content: center; border-radius: 14px; color: var(--mode-color); background: var(--mode-bg); font-size: 14px; font-weight: 800; }
.mode-mark span { display: inline-block; margin-right: 1px; font-size: 21px; line-height: .8; }
.mode-meta h3 { margin: 0; font-size: 17px; }
.mode-meta p { overflow: hidden; margin: 5px 0 0; color: var(--color-text-muted); font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.mode-beginner { --mode-color: #a45d1c; --mode-bg: #fff0d8; }
.mode-proficient { --mode-color: #8b6b29; --mode-bg: #f8f0d8; }
.mode-challenge { --mode-color: #9a4e43; --mode-bg: #fae9e1; }
.weight-grid { display: grid; grid-template-columns: repeat(3, minmax(82px, 1fr)); gap: 10px; min-width: 0; }
.weight-field { display: grid; gap: 6px; min-width: 0; }
.weight-field > span { color: var(--color-text-muted); font-size: 12px; font-weight: 750; }
.weight-field :deep(.el-input-number) { width: 100%; }
.weight-field :deep(.el-input__wrapper), .count-input :deep(.el-input__wrapper) { min-height: 44px; border-radius: 11px; box-shadow: 0 0 0 1px #e7d9c7 inset; }
.weight-field :deep(.el-input__inner), .count-input :deep(.el-input__inner) { color: var(--color-text); font-weight: 700; }
.weight-field :deep(.el-input-number__decrease), .weight-field :deep(.el-input-number__increase), .count-input :deep(.el-input-number__decrease), .count-input :deep(.el-input-number__increase) { color: var(--color-text-muted); }
.total-box { display: grid; justify-items: end; gap: 2px; min-width: 0; padding-left: 18px; border-left: 1px solid #ebdbc9; color: var(--color-text-muted); }
.total-box > span { font-size: 12px; font-weight: 700; }
.total-box strong { color: var(--color-text); font-size: 24px; line-height: 1.1; }
.total-box small { display: flex; min-width: 0; align-items: center; justify-self: stretch; justify-content: flex-end; gap: 4px; color: var(--color-success); font-size: 11px; line-height: 1.35; text-align: right; white-space: normal; }
.total-box small i { font-style: normal; font-weight: 800; }
.total-box.invalid strong, .total-box.invalid small { color: var(--color-danger); }
.save-bar { display: flex; align-items: center; justify-content: space-between; gap: 24px; padding: 18px 20px 18px 24px; border: 1px solid #efdbc1; border-radius: 18px; background: var(--color-surface-accent); }
.save-bar strong { display: block; color: var(--color-text); font-size: 14px; }
.save-bar p { margin: 4px 0 0; color: var(--color-text-muted); font-size: 13px; }
.save-bar button { display: inline-flex; min-height: 46px; align-items: center; gap: 18px; border: 0; border-radius: var(--radius-button); padding: 0 18px 0 20px; color: #fff; background: var(--color-action); font-weight: 750; transition: background-color 160ms ease, transform 160ms ease; }
.save-bar button:hover:not(:disabled) { background: var(--color-action-hover); transform: translateY(-1px); }
.save-bar button:active:not(:disabled) { transform: translateY(0); }
.save-bar button span { font-size: 20px; font-weight: 400; line-height: 1; }
.save-bar button:disabled { opacity: .65; }
@media (max-width: 1150px) {
  .mode-card { grid-template-columns: minmax(180px, 1fr) minmax(300px, 1.55fr); }
  .total-box { grid-column: 1 / -1; grid-template-columns: auto auto 1fr; justify-items: start; align-items: center; gap: 8px; padding: 12px 0 0; border-top: 1px solid #ebdbc9; border-left: 0; }
  .total-box strong { margin-left: 4px; }
  .total-box small { margin-left: 4px; justify-self: start; justify-content: flex-start; text-align: left; }
}
@media (max-width: 1023px) {
  .admin-content { width: min(100% - 40px, 760px); padding-top: 36px; }
  .page-header { margin-bottom: 24px; }
}
@media (max-width: 680px) {
  .admin-content { width: min(100% - 32px, 560px); padding-top: 28px; }
  .page-header, .section-header, .count-card, .save-bar { align-items: flex-start; flex-direction: column; }
  .strategy-badge { width: 100%; justify-content: space-between; }
  .count-card, .strategy-card { padding: 22px 18px; }
  .count-control { width: 100%; justify-items: start; }
  .count-input :deep(.el-input-number) { width: 100%; }
  .count-input { width: 100%; }
  .section-note { margin-top: 10px; }
  .mode-card { grid-template-columns: 1fr; gap: 18px; padding: 18px; }
  .weight-grid { gap: 8px; }
  .total-box { grid-column: auto; }
  .save-bar { padding: 18px; }
  .save-bar button { width: 100%; justify-content: center; }
}
</style>
