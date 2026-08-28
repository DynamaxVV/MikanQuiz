<script setup lang="ts">
import { computed, ref } from 'vue';
import AdminShell from '@/components/AdminShell.vue';
import { api, ApiError } from '@/api/client';
import type { ConfigImportPreview } from '@/types';

const file = ref<File | null>(null);
const preview = ref<ConfigImportPreview | null>(null);
const loading = ref(false);
const importing = ref(false);
const exporting = ref(false);
const error = ref('');
const success = ref('');
const fileInput = ref<HTMLInputElement | null>(null);
const questionFile = ref<File | null>(null);
const questionExporting = ref(false);
const questionImporting = ref(false);
const questionNotice = ref('');
const questionError = ref('');
const questionImportResult = ref<QuestionImportResult | null>(null);
const questionFileInput = ref<HTMLInputElement | null>(null);

interface QuestionImportResult {
  total: number;
  created: number;
  failed: number;
  errors: string[];
}

const scopeItems = ['字体分区与快捷项', '题目、难度与答案', '出题策略与字体预设', '嵌字笔记分区与卡片'];

const diffRows = computed(() => {
  const diff = preview.value?.diff;
  if (!diff) return [];
  return [
    ['分区', diff.option_groups_added, diff.option_groups_deleted, diff.option_groups_updated],
    ['字体', diff.font_options_added, diff.font_options_deleted, diff.font_options_updated],
    ['题目', diff.questions_added, diff.questions_deleted, diff.questions_updated],
    ['笔记分区', diff.reference_sections_added, diff.reference_sections_deleted, diff.reference_sections_updated],
    ['笔记卡片', diff.reference_cards_added, diff.reference_cards_deleted, diff.reference_cards_updated],
    ['出题设置', 0, 0, diff.settings_changed],
  ] as Array<[string, number, number, number]>;
});

const displayedQuestionErrors = computed(() => questionImportResult.value?.errors.slice(0, 3) ?? []);

function chooseFile(): void { fileInput.value?.click(); }

function chooseQuestionFile(): void { questionFileInput.value?.click(); }

function onFileChange(event: Event): void {
  const selected = (event.target as HTMLInputElement).files?.[0] ?? null;
  file.value = selected;
  preview.value = null;
  error.value = '';
  success.value = '';
}

function onQuestionFileChange(event: Event): void {
  questionFile.value = (event.target as HTMLInputElement).files?.[0] ?? null;
  questionNotice.value = '';
  questionError.value = '';
  questionImportResult.value = null;
}

function formatFileSize(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${Math.ceil(size / 1024)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

async function exportConfig(): Promise<void> {
  if (exporting.value || loading.value || importing.value) return;
  exporting.value = true;
  error.value = '';
  success.value = '';
  try {
    await api.exportConfig();
    success.value = '配置文件已下载。';
  } catch (cause) {
    error.value = errorMessage(cause, '配置导出失败，请稍后重试。');
  } finally {
    exporting.value = false;
  }
}

async function exportQuestionBank(): Promise<void> {
  if (questionExporting.value || questionImporting.value) return;
  questionExporting.value = true;
  questionNotice.value = '';
  questionError.value = '';
  try {
    await api.exportQuestions();
    questionNotice.value = '题库 JSON 已下载。';
  } catch (cause) {
    questionError.value = errorMessage(cause, '题库导出失败，请稍后重试。');
  } finally {
    questionExporting.value = false;
  }
}

async function importQuestionBank(): Promise<void> {
  if (!questionFile.value || questionImporting.value || questionExporting.value) return;
  questionImporting.value = true;
  questionNotice.value = '';
  questionError.value = '';
  questionImportResult.value = null;
  try {
    const result = await api.importQuestions(questionFile.value);
    questionImportResult.value = result;
    questionNotice.value = result.failed
      ? `题库导入完成：读取 ${result.total} 题，新增 ${result.created} 题，${result.failed} 题未导入。`
      : `题库导入完成：新增 ${result.created} 题。`;
  } catch (cause) {
    questionError.value = errorMessage(cause, '题库导入失败，请检查 JSON 文件后重试。');
  } finally {
    questionImporting.value = false;
  }
}

function resetQuestionFile(): void {
  questionFile.value = null;
  questionNotice.value = '';
  questionError.value = '';
  questionImportResult.value = null;
  if (questionFileInput.value) questionFileInput.value.value = '';
}

async function validate(): Promise<void> {
  if (!file.value) return;
  loading.value = true;
  error.value = '';
  success.value = '';
  try { preview.value = await api.validateConfig(file.value); }
  catch (cause) { error.value = errorMessage(cause, '配置校验失败，请检查文件后重试。'); }
  finally { loading.value = false; }
}

async function importConfig(): Promise<void> {
  if (!file.value || !preview.value || importing.value) return;
  const confirmed = window.confirm('导入将替换题库、字体分区、出题设置和嵌字笔记。管理员账号、答题会话与历史提交不会被删除。确定继续吗？');
  if (!confirmed) return;
  importing.value = true;
  error.value = '';
  success.value = '';
  try {
    const result = await api.importConfig(file.value, preview.value);
    success.value = `配置已导入：新增 ${result.diff.questions_added} 题，删除 ${result.diff.questions_deleted} 题。`;
    preview.value = null;
  } catch (cause) { error.value = errorMessage(cause, '配置导入失败，数据库未完成替换。'); }
  finally { importing.value = false; }
}

function errorMessage(cause: unknown, fallback: string): string {
  if (!(cause instanceof ApiError)) return fallback;
  if (cause.details?.length) {
    const detail = cause.details[0]?.message;
    return `${cause.message}（${detail ? String(detail) : '请查看错误详情'}）`;
  }
  return cause.message || fallback;
}

function reset(): void {
  file.value = null;
  preview.value = null;
  error.value = '';
  success.value = '';
  if (fileInput.value) fileInput.value.value = '';
}
</script>

<template>
  <AdminShell>
    <section class="admin-content" aria-labelledby="config-transfer-title">
      <header class="page-header">
        <div class="page-intro">
          <div class="eyebrow-row">
            <p class="eyebrow">配置迁移</p>
            <span class="version-tag">JSON · v1</span>
          </div>
          <h1 id="config-transfer-title" class="page-title">完整 JSON 配置</h1>
          <p class="page-description">把题库、字体分区、出题设置与嵌字笔记整理成一份可审阅、可恢复的配置文件。</p>
        </div>
        <button
          type="button"
          class="transfer-button transfer-button--secondary export-button"
          :disabled="loading || importing || exporting"
          @click="exportConfig"
        >
          <span class="button-icon" aria-hidden="true">↓</span>
          {{ exporting ? '正在准备…' : '导出当前配置' }}
        </button>
      </header>

      <div class="migration-layout">
        <section class="card transfer-card" aria-labelledby="import-title">
          <div class="section-heading">
            <span class="step-number">01</span>
            <div class="section-copy">
              <h2 id="import-title">选择配置文件</h2>
              <p>只接受本系统导出的 <code>mikanquiz-admin-config.json</code>，文件会先在服务器只读校验。</p>
            </div>
          </div>

          <input ref="fileInput" class="sr-only" type="file" accept="application/json,.json" @change="onFileChange" />

          <div class="file-picker" :class="{ selected: file }">
            <div class="file-summary">
              <span class="file-icon" aria-hidden="true">JSON</span>
              <div class="file-copy">
                <strong>{{ file?.name ?? '尚未选择文件' }}</strong>
                <p>{{ file ? `${formatFileSize(file.size)} · 等待生成预览` : '建议先导出一份当前配置作为备份' }}</p>
              </div>
            </div>
            <button type="button" class="transfer-button transfer-button--outline" @click="chooseFile">选择 JSON</button>
          </div>

          <div class="action-row">
            <button
              type="button"
              class="transfer-button transfer-button--primary"
              :disabled="!file || loading || importing || exporting"
              @click="validate"
            >
              <span v-if="loading" class="button-spinner" aria-hidden="true"></span>
              {{ loading ? '正在校验…' : '校验并生成预览' }}
            </button>
            <button v-if="file" type="button" class="quiet-button" @click="reset">清除文件</button>
          </div>
        </section>

        <aside class="card scope-card" aria-labelledby="scope-title">
          <p class="card-kicker">文件内容</p>
          <h2 id="scope-title">一份文件，完整迁移</h2>
          <p class="scope-description">导出的 JSON 使用稳定配置键，适合备份、审阅和在另一套环境恢复。</p>
          <ul class="scope-list">
            <li v-for="item in scopeItems" :key="item">
              <span class="check-mark" aria-hidden="true">✓</span>
              <span>{{ item }}</span>
            </li>
          </ul>
          <p class="scope-footnote">管理员账号、答题会话与历史提交不会随配置文件迁移。</p>
        </aside>
      </div>

      <section class="card question-bank-card" aria-labelledby="question-bank-title">
        <div class="section-heading">
          <span class="step-number step-number--tool">QB</span>
          <div class="section-copy">
            <p class="card-kicker">题库工具</p>
            <h2 id="question-bank-title">单独迁移题库</h2>
            <p>只处理题目数据，适合日常批量维护；不会替换字体分区、出题策略或嵌字笔记。</p>
          </div>
        </div>

        <div class="question-tool-grid">
          <article class="question-tool">
            <div class="question-tool-top">
              <span class="tool-mark" aria-hidden="true">↓</span>
              <div>
                <h3>导出题库</h3>
                <p>下载当前全部题目，包含题干、图片地址、难度、答案和解析。</p>
              </div>
            </div>
            <button
              type="button"
              class="transfer-button transfer-button--outline"
              :disabled="questionExporting || questionImporting"
              @click="exportQuestionBank"
            >
              {{ questionExporting ? '正在准备…' : '导出题库 JSON' }}
            </button>
          </article>

          <article class="question-tool question-tool--import">
            <div class="question-tool-top">
              <span class="tool-mark" aria-hidden="true">↑</span>
              <div>
                <h3>导入题库</h3>
                <p>导入会追加有效题目，已有题目不会被覆盖；失败项会保留在结果中。</p>
              </div>
            </div>

            <input ref="questionFileInput" class="sr-only" type="file" accept="application/json,.json" @change="onQuestionFileChange" />
            <div class="file-picker question-file-picker" :class="{ selected: questionFile }">
              <div class="file-summary">
                <span class="file-icon" aria-hidden="true">JSON</span>
                <div class="file-copy">
                  <strong>{{ questionFile?.name ?? '尚未选择题库文件' }}</strong>
                  <p>{{ questionFile ? `${formatFileSize(questionFile.size)} · 准备导入` : '选择由题库导出生成的 questions.json' }}</p>
                </div>
              </div>
              <button type="button" class="transfer-button transfer-button--outline" :disabled="questionImporting || questionExporting" @click="chooseQuestionFile">选择文件</button>
            </div>
            <div class="question-import-actions">
              <button
                type="button"
                class="transfer-button transfer-button--primary"
                :disabled="!questionFile || questionImporting || questionExporting"
                @click="importQuestionBank"
              >
                {{ questionImporting ? '正在导入…' : '导入到当前题库' }}
              </button>
              <button v-if="questionFile" type="button" class="quiet-button" @click="resetQuestionFile">清除文件</button>
            </div>
          </article>
        </div>

        <div v-if="questionError" class="question-feedback question-feedback--error" role="alert">
          <span class="feedback-mark" aria-hidden="true">!</span>
          <span>{{ questionError }}</span>
        </div>
        <div v-if="questionNotice" class="question-feedback question-feedback--success" role="status">
          <span class="feedback-mark" aria-hidden="true">✓</span>
          <span>{{ questionNotice }}</span>
        </div>

        <div v-if="questionImportResult" class="question-result" :class="{ 'question-result--partial': questionImportResult.failed }">
          <div class="question-result-heading">
            <div>
              <p class="card-kicker">导入结果</p>
              <strong>{{ questionImportResult.failed ? '部分题目未导入' : '题库已追加' }}</strong>
            </div>
            <span>原有题目未被覆盖</span>
          </div>
          <div class="question-result-metrics">
            <div><strong>{{ questionImportResult.total }}</strong><span>读取</span></div>
            <div><strong>{{ questionImportResult.created }}</strong><span>新增</span></div>
            <div><strong>{{ questionImportResult.failed }}</strong><span>未导入</span></div>
          </div>
          <div v-if="questionImportResult.errors.length" class="question-error-list">
            <p>未导入原因（最多显示 3 条）</p>
            <ul>
              <li v-for="item in displayedQuestionErrors" :key="item">{{ item }}</li>
            </ul>
            <span v-if="questionImportResult.errors.length > displayedQuestionErrors.length">还有 {{ questionImportResult.errors.length - displayedQuestionErrors.length }} 条原因未展开。</span>
          </div>
        </div>
      </section>

      <div v-if="error" class="feedback feedback--error" role="alert">
        <span class="feedback-mark" aria-hidden="true">!</span>
        <span>{{ error }}</span>
      </div>
      <div v-if="success" class="feedback feedback--success" role="status">
        <span class="feedback-mark" aria-hidden="true">✓</span>
        <span>{{ success }}</span>
      </div>

      <section v-if="preview" class="card preview-card" aria-labelledby="preview-title">
        <div class="section-heading">
          <span class="step-number">02</span>
          <div class="section-copy">
            <h2 id="preview-title">替换预览</h2>
            <p>服务端按稳定 config_key 计算差异，整数数据库 ID 不会被写入文件。</p>
          </div>
        </div>

        <div class="hash-grid">
          <div class="hash-item">
            <span>当前配置</span>
            <code>{{ preview.currentHash }}</code>
          </div>
          <div class="hash-item">
            <span>导入文件</span>
            <code>{{ preview.incomingHash }}</code>
          </div>
        </div>

        <div class="diff-table-wrap">
          <table class="diff-table">
            <thead>
              <tr><th>对象</th><th>新增</th><th>删除</th><th>更新</th></tr>
            </thead>
            <tbody>
              <tr v-for="row in diffRows" :key="row[0]">
                <th>{{ row[0] }}</th><td>{{ row[1] }}</td><td>{{ row[2] }}</td><td>{{ row[3] }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <ul v-if="preview.warnings.length" class="warnings">
          <li v-for="warning in preview.warnings" :key="warning">{{ warning }}</li>
        </ul>

        <div class="preview-footer">
          <div class="danger-note">
            <strong>这是替换操作</strong>
            <span>管理员、答题会话、提交历史和已上传的原始图片/字体文件不会被删除；配置实体将按文件内容替换。</span>
          </div>
          <button
            type="button"
            class="transfer-button transfer-button--primary confirm-button"
            :disabled="!preview.canImport || importing"
            @click="importConfig"
          >
            {{ importing ? '正在导入…' : '确认替换当前配置' }}
          </button>
        </div>
      </section>
    </section>
  </AdminShell>
</template>

<style scoped>
.admin-content {
  width: min(1120px, calc(100% - 48px));
  min-width: 0;
  margin: 0 auto;
  padding: clamp(32px, 5vw, 58px) 0 80px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 32px;
  min-width: 0;
  margin-bottom: 30px;
}

.page-intro { min-width: 0; }

.eyebrow-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.eyebrow-row .eyebrow { margin: 0; }

.version-tag {
  display: inline-flex;
  min-height: 24px;
  align-items: center;
  border: 1px solid #edcfac;
  border-radius: 999px;
  padding: 0 9px;
  color: #93551e;
  background: var(--color-surface-accent);
  font-size: 11px;
  font-weight: 750;
  letter-spacing: .03em;
}

.page-title {
  max-width: 680px;
  margin: 12px 0 10px;
  font-size: clamp(32px, 4vw, 48px);
  line-height: 1.08;
  letter-spacing: -.04em;
}

.page-description {
  max-width: 680px;
  margin: 0;
  font-size: 15px;
  line-height: 1.7;
}

.transfer-button {
  display: inline-flex;
  min-height: 42px;
  align-items: center;
  justify-content: center;
  gap: 8px;
  flex-shrink: 0;
  border: 1px solid transparent;
  border-radius: 12px;
  padding: 0 16px;
  font-size: 13px;
  font-weight: 750;
  line-height: 1.2;
  white-space: nowrap;
  transition: background-color 150ms ease-out, border-color 150ms ease-out, box-shadow 150ms ease-out, transform 120ms ease-out;
}

.transfer-button:active:not(:disabled) { transform: scale(.98); }
.transfer-button:disabled { opacity: .55; }
.transfer-button--primary { border-color: var(--color-action); color: #fff; background: var(--color-action); }
.transfer-button--secondary { border-color: #d8b789; color: #7e431f; background: var(--color-surface-accent); }
.transfer-button--outline { border-color: #d8b789; color: var(--color-action); background: #fff; }
.button-icon { font-size: 18px; font-weight: 500; line-height: 1; }
.button-spinner { width: 13px; height: 13px; border: 2px solid rgba(255, 255, 255, .45); border-top-color: #fff; border-radius: 50%; animation: transfer-spin 700ms linear infinite; }

@media (hover: hover) and (pointer: fine) {
  .transfer-button:hover:not(:disabled) { box-shadow: 0 6px 16px rgba(116, 72, 20, .1); }
  .transfer-button--primary:hover:not(:disabled) { background: var(--color-action-hover); }
  .transfer-button--secondary:hover:not(:disabled) { border-color: #c98748; background: #ffe8c2; }
  .transfer-button--outline:hover:not(:disabled) { border-color: #c98748; background: #fff8ed; }
  .quiet-button:hover { color: var(--color-action); background: var(--color-surface-warm); }
}

@keyframes transfer-spin { to { transform: rotate(360deg); } }

.migration-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(260px, .75fr);
  gap: 16px;
  min-width: 0;
}

.transfer-card, .scope-card, .preview-card {
  min-width: 0;
  padding: 24px;
}

.transfer-card, .preview-card { display: grid; gap: 22px; }

.section-heading {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  align-items: start;
  gap: 13px;
  min-width: 0;
}

.step-number {
  display: inline-grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border-radius: 11px;
  color: var(--color-action);
  background: var(--color-surface-accent);
  font-size: 11px;
  font-weight: 850;
  letter-spacing: .05em;
}

.section-copy { min-width: 0; }
.section-heading h2, .scope-card h2 { margin: 0 0 6px; color: var(--color-text); font-size: 19px; line-height: 1.25; }
.section-heading p, .scope-description { margin: 0; color: var(--color-text-muted); font-size: 13px; line-height: 1.65; text-wrap: pretty; }
.section-heading code { color: var(--color-text); font-size: 12px; overflow-wrap: anywhere; }

.file-picker {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 18px;
  min-width: 0;
  padding: 16px;
  border: 1px dashed #d8b789;
  border-radius: 15px;
  background: #fffbf5;
}

.file-picker.selected { border-style: solid; border-color: #c98748; background: #fff6e8; }
.file-summary { display: flex; align-items: center; gap: 12px; min-width: 0; }
.file-icon { display: inline-grid; width: 42px; height: 42px; flex: 0 0 42px; place-items: center; border: 1px solid #edcfac; border-radius: 11px; color: var(--color-action); background: #fff; font-size: 10px; font-weight: 850; letter-spacing: .04em; }
.file-copy { min-width: 0; }
.file-copy strong { display: block; overflow-wrap: anywhere; color: var(--color-text); font-size: 14px; line-height: 1.4; }
.file-copy p { margin: 4px 0 0; color: var(--color-text-muted); font-size: 12px; line-height: 1.45; }

.action-row { display: flex; align-items: center; gap: 12px; min-width: 0; }
.quiet-button { min-height: 40px; border: 0; border-radius: 10px; padding: 0 9px; color: var(--color-text-muted); background: transparent; font-size: 13px; font-weight: 650; }

.scope-card { background: #fffdf9; }
.card-kicker { margin: 0 0 10px; color: var(--color-accent); font-size: 11px; font-weight: 800; letter-spacing: .1em; text-transform: uppercase; }
.scope-description { margin-bottom: 20px; }
.scope-list { display: grid; gap: 11px; margin: 0; padding: 0; list-style: none; color: var(--color-text); font-size: 13px; font-weight: 650; }
.scope-list li { display: flex; align-items: flex-start; gap: 9px; min-width: 0; }
.check-mark { display: inline-grid; width: 18px; height: 18px; flex: 0 0 18px; place-items: center; border-radius: 50%; color: #2f7048; background: #e9f5e8; font-size: 12px; font-weight: 850; }
.scope-footnote { margin: 22px 0 0; padding-top: 15px; border-top: 1px solid var(--color-border); color: var(--color-text-muted); font-size: 12px; line-height: 1.6; }

.question-bank-card { display: grid; gap: 20px; min-width: 0; margin-top: 16px; padding: 24px; }
.step-number--tool { color: #93551e; background: #fff8ed; font-size: 10px; letter-spacing: .02em; }
.question-bank-card .section-heading .card-kicker { margin-bottom: 8px; }
.question-tool-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; min-width: 0; }
.question-tool { display: grid; align-content: start; gap: 16px; min-width: 0; padding: 18px; border: 1px solid #f0dfc9; border-radius: 15px; background: #fffaf2; }
.question-tool--import { background: #fffdf9; }
.question-tool-top { display: grid; grid-template-columns: 34px minmax(0, 1fr); align-items: start; gap: 12px; min-width: 0; }
.tool-mark { display: inline-grid; width: 34px; height: 34px; place-items: center; border: 1px solid #edcfac; border-radius: 10px; color: var(--color-action); background: #fff; font-size: 18px; line-height: 1; }
.question-tool h3 { margin: 0 0 5px; color: var(--color-text); font-size: 16px; line-height: 1.3; }
.question-tool p { margin: 0; color: var(--color-text-muted); font-size: 12px; line-height: 1.65; text-wrap: pretty; }
.question-tool > .transfer-button { justify-self: start; }
.question-file-picker { padding: 12px; border-radius: 12px; }
.question-file-picker .file-icon { width: 36px; height: 36px; flex-basis: 36px; border-radius: 9px; }
.question-file-picker .file-copy strong { font-size: 13px; }
.question-file-picker .transfer-button { padding: 0 12px; }
.question-import-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; }
.question-feedback { display: flex; align-items: flex-start; gap: 10px; min-width: 0; padding: 12px 14px; border: 1px solid; border-radius: 11px; font-size: 13px; line-height: 1.55; overflow-wrap: anywhere; }
.question-feedback--error { color: #7d2f2a; border-color: #ecc3be; background: #fff0ee; }
.question-feedback--success { color: #21602f; border-color: #c5e5cb; background: #edf8ef; }
.question-result { display: grid; gap: 14px; min-width: 0; padding: 16px; border: 1px solid #c5e5cb; border-radius: 12px; background: #f5fbf4; }
.question-result--partial { border-color: #efd7af; background: #fffaf0; }
.question-result-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; min-width: 0; }
.question-result-heading .card-kicker { margin-bottom: 5px; }
.question-result-heading strong { color: var(--color-text); font-size: 15px; }
.question-result-heading > span { color: var(--color-text-muted); font-size: 12px; }
.question-result-metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
.question-result-metrics div { display: grid; gap: 2px; min-width: 0; padding: 10px 12px; border-radius: 9px; background: rgba(255, 255, 255, .72); }
.question-result-metrics strong { color: var(--color-text); font-size: 22px; line-height: 1; }
.question-result-metrics span { color: var(--color-text-muted); font-size: 11px; }
.question-error-list { min-width: 0; color: #805315; font-size: 12px; line-height: 1.6; }
.question-error-list p { margin: 0 0 4px; color: inherit; font-weight: 750; }
.question-error-list ul { margin: 0; padding-left: 20px; overflow-wrap: anywhere; }
.question-error-list > span { display: block; margin-top: 4px; color: var(--color-text-muted); }

.feedback { display: flex; align-items: flex-start; gap: 10px; min-width: 0; margin-top: 16px; padding: 13px 15px; border: 1px solid; border-radius: 12px; font-size: 13px; line-height: 1.55; overflow-wrap: anywhere; }
.feedback--error { color: #7d2f2a; border-color: #ecc3be; background: #fff0ee; }
.feedback--success { color: #21602f; border-color: #c5e5cb; background: #edf8ef; }
.feedback-mark { display: inline-grid; width: 20px; height: 20px; flex: 0 0 20px; place-items: center; border-radius: 50%; color: #fff; font-size: 12px; font-weight: 850; }
.feedback--error .feedback-mark { background: #b5483f; }.feedback--success .feedback-mark { background: #39864a; }

.preview-card { margin-top: 16px; }
.hash-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; min-width: 0; }
.hash-item { display: grid; gap: 7px; min-width: 0; padding: 13px 14px; border: 1px solid #f0dfc9; border-radius: 11px; background: #fff8ed; }
.hash-item > span { color: var(--color-text-muted); font-size: 11px; font-weight: 750; }
.hash-item code { min-width: 0; overflow-wrap: anywhere; color: var(--color-text); font-size: 11px; line-height: 1.5; }
.diff-table-wrap { width: 100%; min-width: 0; overflow-x: auto; border: 1px solid var(--color-border); border-radius: 12px; }
.diff-table { width: 100%; min-width: 520px; border-collapse: collapse; font-size: 13px; }
.diff-table th, .diff-table td { padding: 11px 14px; border-bottom: 1px solid var(--color-border); text-align: right; white-space: nowrap; }
.diff-table tr:last-child th, .diff-table tr:last-child td { border-bottom: 0; }
.diff-table th:first-child, .diff-table tbody th { text-align: left; }
.diff-table thead th { color: var(--color-text-muted); background: #fffaf2; font-size: 11px; font-weight: 750; }
.diff-table tbody th { color: var(--color-text); font-weight: 700; }
.warnings { margin: 0; padding: 12px 16px 12px 32px; border-radius: 10px; color: #805315; background: #fff3cf; font-size: 13px; line-height: 1.7; overflow-wrap: anywhere; }
.preview-footer { display: flex; align-items: center; justify-content: space-between; gap: 16px; min-width: 0; }
.danger-note { display: grid; gap: 4px; min-width: 0; padding: 13px 15px; border-left: 3px solid #d9794c; border-radius: 8px; color: #78412d; background: #fff0e8; font-size: 12px; line-height: 1.6; }
.danger-note strong { font-size: 13px; }.danger-note span { overflow-wrap: anywhere; }.confirm-button { margin-left: auto; }

code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }

@media (max-width: 900px) {
  .admin-content { width: min(calc(100% - 32px), 720px); padding-top: 32px; }
  .page-header { flex-direction: column; gap: 18px; }
  .export-button { width: 100%; }
  .migration-layout { grid-template-columns: 1fr; }
  .question-tool-grid { grid-template-columns: 1fr; }
}

@media (max-width: 600px) {
  .admin-content { width: calc(100% - 32px); padding-bottom: 56px; }
  .transfer-card, .scope-card, .question-bank-card, .preview-card { padding: 18px; }
  .page-title { font-size: 32px; }
  .file-picker { grid-template-columns: 1fr; align-items: stretch; }
  .file-picker .transfer-button, .action-row .transfer-button, .confirm-button { width: 100%; }
  .action-row { align-items: stretch; flex-direction: column; }
  .quiet-button { align-self: flex-start; }
  .question-tool { padding: 16px; }
  .question-tool > .transfer-button, .question-import-actions .transfer-button { width: 100%; }
  .question-import-actions { align-items: stretch; flex-direction: column; }
  .question-import-actions .quiet-button { align-self: flex-start; }
  .question-result-heading { align-items: flex-start; flex-direction: column; gap: 6px; }
  .hash-grid { grid-template-columns: 1fr; }
  .preview-footer { align-items: stretch; flex-direction: column; }
  .confirm-button { margin-left: 0; }
}

@media (prefers-reduced-motion: reduce) {
  .button-spinner { animation: none; }
}
</style>
