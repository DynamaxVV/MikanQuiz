<script setup lang="ts">
import { computed, ref } from 'vue';
import AdminShell from '@/components/AdminShell.vue';
import { api, ApiError } from '@/api/client';
import type { ConfigImportPreview } from '@/types';

interface QuestionImportResult {
  total: number;
  created: number;
  failed: number;
  errors: string[];
}

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

const transferBusy = computed(() => loading.value || importing.value || exporting.value);
const previewIsSettings = computed(() => preview.value?.mode === 'settings');
const previewModeLabel = computed(() => (previewIsSettings.value ? '设置配置 · 保留题库' : '完整配置 · 包含题库'));
const previewTitle = computed(() => (previewIsSettings.value ? '检查设置配置' : '检查完整配置'));
const previewDescription = computed(() => (
  previewIsSettings.value
    ? '只替换设置与嵌字笔记，当前题库保持不变。'
    : '替换题库与设置内容，管理员账号和历史记录保持不变。'
));
const previewActionLabel = computed(() => (previewIsSettings.value ? '确认导入设置' : '确认替换全部配置'));
const previewDangerTitle = computed(() => (previewIsSettings.value ? '设置配置不会删除题目' : '这是全部配置替换'));
const previewDangerText = computed(() => (
  previewIsSettings.value
    ? '题目和提交历史保留不变；字体选项变更可能使个别题目的正确字体需要重新检查。'
    : '管理员账号、答题会话、提交历史和已上传的原始图片/字体文件不会被删除；配置实体按文件内容替换。'
));
const displayedQuestionErrors = computed(() => questionImportResult.value?.errors.slice(0, 3) ?? []);

const diffRows = computed(() => {
  const diff = preview.value?.diff;
  if (!diff) return [];
  const rows: Array<[string, number, number, number]> = [
    ['字体分区', diff.option_groups_added, diff.option_groups_deleted, diff.option_groups_updated],
    ['字体选项', diff.font_options_added, diff.font_options_deleted, diff.font_options_updated],
    ['嵌字笔记分区', diff.reference_sections_added, diff.reference_sections_deleted, diff.reference_sections_updated],
    ['嵌字笔记卡片', diff.reference_cards_added, diff.reference_cards_deleted, diff.reference_cards_updated],
    ['出题设置', 0, 0, diff.settings_changed],
  ];
  if (!previewIsSettings.value) rows.splice(2, 0, ['题库', diff.questions_added, diff.questions_deleted, diff.questions_updated]);
  return rows;
});

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
  if (transferBusy.value) return;
  exporting.value = true;
  error.value = '';
  success.value = '';
  try {
    await api.exportConfig();
    success.value = '完整配置（含题库）已下载。';
  } catch (cause) {
    error.value = errorMessage(cause, '完整配置导出失败，请稍后重试。');
  } finally {
    exporting.value = false;
  }
}

async function exportSettingsConfig(): Promise<void> {
  if (transferBusy.value) return;
  exporting.value = true;
  error.value = '';
  success.value = '';
  try {
    await api.exportSettingsConfig();
    success.value = '设置配置已下载（不含题库）。';
  } catch (cause) {
    error.value = errorMessage(cause, '设置配置导出失败，请稍后重试。');
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
    clearQuestionSelection();
  } catch (cause) {
    questionError.value = errorMessage(cause, '题库导入失败，请检查 JSON 文件后重试。');
  } finally {
    questionImporting.value = false;
  }
}

function clearQuestionSelection(): void {
  questionFile.value = null;
  if (questionFileInput.value) questionFileInput.value.value = '';
}

function resetQuestionFile(): void {
  clearQuestionSelection();
  questionNotice.value = '';
  questionError.value = '';
  questionImportResult.value = null;
}

async function validate(): Promise<void> {
  if (!file.value) return;
  loading.value = true;
  error.value = '';
  success.value = '';
  try {
    preview.value = await api.validateConfig(file.value);
  } catch (cause) {
    error.value = errorMessage(cause, '配置校验失败，请检查文件后重试。');
  } finally {
    loading.value = false;
  }
}

async function importConfig(): Promise<void> {
  if (!file.value || !preview.value || importing.value) return;
  const message = previewIsSettings.value
    ? '导入只会替换设置、字体分区和嵌字笔记，当前题库与提交历史不会被删除。确定继续吗？'
    : '导入将替换题库、字体分区、出题设置和嵌字笔记。管理员账号、答题会话与历史提交不会被删除。确定继续吗？';
  if (!window.confirm(message)) return;

  importing.value = true;
  error.value = '';
  success.value = '';
  try {
    const result = await api.importConfig(file.value, preview.value);
    success.value = result.mode === 'settings'
      ? '设置配置已导入，当前题库保持不变。'
      : `完整配置已导入：新增 ${result.diff.questions_added} 题，删除 ${result.diff.questions_deleted} 题。`;
    preview.value = null;
  } catch (cause) {
    error.value = errorMessage(cause, '配置导入失败，数据库未完成替换。');
  } finally {
    importing.value = false;
  }
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
          <h1 id="config-transfer-title" class="page-title">配置迁移</h1>
        </div>
        <button
          type="button"
          class="transfer-button transfer-button--primary export-all-button"
          :disabled="transferBusy"
          @click="exportConfig"
        >
          <span class="button-label">{{ exporting ? '正在准备…' : '导出全部配置' }}</span>
          <span class="button-detail">包含题库 · 字体 · 策略 · 嵌字笔记</span>
        </button>
      </header>

      <section class="transfer-layout migration-flow" aria-label="配置迁移流程">
        <section class="card step-card config-card" aria-labelledby="import-title">
          <header class="panel-heading">
            <span class="step-mark" aria-hidden="true">01</span>
            <div class="section-copy">
              <div class="panel-kicker-row">
                <p class="panel-kicker">导入配置</p>
                <span class="panel-format">JSON</span>
              </div>
              <h2 id="import-title">选择配置文件</h2>
              <p>支持完整配置或设置配置；先校验预览，再确认导入。</p>
            </div>
          </header>

          <div class="scope-grid" aria-label="配置文件范围">
            <div class="scope-option">
              <span class="scope-mark" aria-hidden="true">全量</span>
              <div>
                <strong>完整配置</strong>
                <p>含题库，恢复所有可迁移内容</p>
              </div>
            </div>
            <div class="scope-option scope-option--settings">
              <span class="scope-mark" aria-hidden="true">设置</span>
              <div>
                <strong>设置配置</strong>
                <p>不含题库，保留当前题库</p>
              </div>
            </div>
          </div>

          <input ref="fileInput" class="sr-only" type="file" accept="application/json,.json" @change="onFileChange" />

          <div class="file-picker" :class="{ selected: file }">
            <div class="file-summary">
              <span class="file-type" aria-hidden="true">JSON</span>
              <div class="file-copy">
                <strong>{{ file?.name ?? '尚未选择配置文件' }}</strong>
                <p>{{ file ? `${formatFileSize(file.size)} · 等待生成预览` : '选择系统导出的配置 JSON 文件' }}</p>
              </div>
            </div>
            <button type="button" class="transfer-button transfer-button--outline" :disabled="transferBusy" @click="chooseFile">
              {{ file ? '更换文件' : '选择 JSON' }}
            </button>
          </div>

          <div class="config-actions">
            <div class="primary-actions">
              <button
                type="button"
                class="transfer-button transfer-button--primary"
                :disabled="!file || transferBusy"
                @click="validate"
              >
                <span v-if="loading" class="button-spinner" aria-hidden="true"></span>
                {{ loading ? '正在校验…' : '校验并生成预览' }}
              </button>
              <button v-if="file" type="button" class="quiet-button" @click="reset">清除文件</button>
            </div>
            <div class="settings-export">
              <div>
                <strong>只迁移设置</strong>
                <span>导出不含题库的配置</span>
              </div>
              <button type="button" class="transfer-button transfer-button--soft" :disabled="transferBusy" @click="exportSettingsConfig">
                {{ exporting ? '正在准备…' : '导出设置配置' }}
              </button>
            </div>
          </div>
        </section>

        <section class="card step-card preview-card" :class="{ 'preview-card--empty': !preview }" aria-labelledby="preview-title">
          <header class="panel-heading">
            <span class="step-mark step-mark--muted" aria-hidden="true">02</span>
            <div class="section-copy">
              <div class="panel-kicker-row">
                <p class="panel-kicker">预览确认</p>
                <span class="panel-format">只读检查</span>
              </div>
              <h2 id="preview-title">{{ preview ? previewTitle : '生成预览后确认' }}</h2>
              <p>{{ preview ? previewDescription : '校验完成后，这里会显示范围、哈希和逐项差异。' }}</p>
            </div>
          </header>

          <div v-if="preview" class="preview-content">
            <div class="preview-banner">
              <div>
                <span class="preview-mode">{{ previewModeLabel }}</span>
                <strong>{{ preview.canImport ? '文件可以导入' : '文件需要修正后再导入' }}</strong>
              </div>
              <span class="preview-hint">服务器检查完成</span>
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
                <strong>{{ previewDangerTitle }}</strong>
                <span>{{ previewDangerText }}</span>
              </div>
              <button
                type="button"
                class="transfer-button transfer-button--primary confirm-button"
                :disabled="!preview.canImport || importing"
                @click="importConfig"
              >
                {{ importing ? '正在导入…' : previewActionLabel }}
              </button>
            </div>
          </div>

          <div v-else class="preview-placeholder">
            <span class="placeholder-label" aria-hidden="true">02</span>
            <div>
              <strong>等待配置文件</strong>
              <p>完成左侧校验后，差异和导入按钮会出现在这里。</p>
            </div>
          </div>
        </section>
      </section>

      <div v-if="error" class="feedback feedback--error" role="alert">
        <span class="feedback-mark" aria-hidden="true">!</span>
        <span>{{ error }}</span>
      </div>
      <div v-if="success" class="feedback feedback--success" role="status">
        <span class="feedback-mark" aria-hidden="true">✓</span>
        <span>{{ success }}</span>
      </div>

      <section class="card question-bank-card" aria-labelledby="question-bank-title">
        <header class="tool-header">
          <div>
            <p class="card-kicker">题库工具</p>
            <h2 id="question-bank-title">独立导入与导出</h2>
            <p>只处理题目数据；导入只追加有效题目，不覆盖已有题目。</p>
          </div>
          <span class="tool-badge">仅追加 · 不覆盖</span>
        </header>

        <div class="question-tool-grid">
          <article class="question-tool">
            <div class="tool-heading">
              <span class="tool-label">导出</span>
              <div>
                <h3>下载题库文件</h3>
                <p>包含题干、图片地址、难度、答案和解析。</p>
              </div>
            </div>
            <div class="tool-footer">
              <span>JSON · 当前全部题目</span>
              <button
                type="button"
                class="transfer-button transfer-button--outline"
                :disabled="questionExporting || questionImporting"
                @click="exportQuestionBank"
              >
                {{ questionExporting ? '正在准备…' : '导出题库 JSON' }}
              </button>
            </div>
          </article>

          <article class="question-tool question-tool--import">
            <div class="tool-heading">
              <span class="tool-label">导入</span>
              <div>
                <h3>追加题库文件</h3>
                <p>服务端逐题校验，并返回新增与失败结果。</p>
              </div>
            </div>

            <input ref="questionFileInput" class="sr-only" type="file" accept="application/json,.json" @change="onQuestionFileChange" />
            <div class="file-picker question-file-picker" :class="{ selected: questionFile }">
              <div class="file-summary">
                <span class="file-type" aria-hidden="true">JSON</span>
                <div class="file-copy">
                  <strong>{{ questionFile?.name ?? '尚未选择题库文件' }}</strong>
                  <p>{{ questionFile ? `${formatFileSize(questionFile.size)} · 准备导入` : '选择包含 questions 数组的 JSON' }}</p>
                </div>
              </div>
              <button type="button" class="transfer-button transfer-button--outline" :disabled="questionImporting || questionExporting" @click="chooseQuestionFile">
                {{ questionFile ? '更换文件' : '选择文件' }}
              </button>
            </div>
            <div class="question-import-actions">
              <button
                type="button"
                class="transfer-button transfer-button--primary"
                :disabled="!questionFile || questionImporting || questionExporting"
                @click="importQuestionBank"
              >
                {{ questionImporting ? '正在导入…' : '追加到当前题库' }}
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
              <li v-for="(item, index) in displayedQuestionErrors" :key="`${index}-${item}`">{{ item }}</li>
            </ul>
            <span v-if="questionImportResult.errors.length > displayedQuestionErrors.length">还有 {{ questionImportResult.errors.length - displayedQuestionErrors.length }} 条原因未展开。</span>
          </div>
        </div>
      </section>
    </section>
  </AdminShell>
</template>

<style scoped>
.admin-content {
  width: min(1240px, calc(100% - 64px));
  min-width: 0;
  margin: 0 auto;
  padding: clamp(32px, 5vw, 56px) 0 72px;
}

.page-header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: flex-start;
  gap: 32px;
  min-width: 0;
  margin-bottom: 30px;
}

.page-intro { min-width: 0; }

.eyebrow-row,
.panel-kicker-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.eyebrow-row .eyebrow { margin: 0; }

.version-tag,
.tool-badge,
.preview-mode {
  display: inline-flex;
  align-items: center;
  border: 1px solid #edcfac;
  border-radius: 999px;
  color: #93551e;
  background: var(--color-surface-accent);
  font-weight: 750;
}

.version-tag {
  min-height: 24px;
  padding: 0 9px;
  font-size: 11px;
  letter-spacing: .03em;
}

.page-title {
  max-width: 760px;
  margin: 12px 0 0;
  font-size: clamp(34px, 4vw, 48px);
  line-height: 1.08;
  letter-spacing: -.04em;
  text-wrap: balance;
}

.transfer-button {
  display: inline-flex;
  min-height: 42px;
  max-width: 100%;
  align-items: center;
  justify-content: center;
  gap: 8px;
  flex-shrink: 0;
  border: 1px solid transparent;
  border-radius: 12px;
  padding: 0 16px;
  color: var(--color-text);
  font-size: 13px;
  font-weight: 750;
  line-height: 1.2;
  white-space: nowrap;
  transition: background-color 150ms ease-out, border-color 150ms ease-out, box-shadow 150ms ease-out, transform 120ms ease-out;
}

.transfer-button:active:not(:disabled) { transform: scale(.98); }
.transfer-button:disabled { opacity: .55; }
.transfer-button--primary { border-color: var(--color-action); color: #fff; background: var(--color-action); }
.transfer-button--outline { border-color: #d8b789; color: var(--color-action); background: #fff; }
.transfer-button--soft { border-color: #edcfac; color: #7e431f; background: var(--color-surface-accent); }

.export-all-button {
  min-width: 214px;
  min-height: 58px;
  align-items: flex-start;
  flex-direction: column;
  gap: 5px;
  border-radius: 16px;
  padding: 12px 16px;
  text-align: left;
}

.button-label { font-size: 15px; }
.button-detail { color: rgba(255, 255, 255, .8); font-size: 11px; font-weight: 600; line-height: 1.35; white-space: normal; }

@media (hover: hover) and (pointer: fine) {
  .transfer-button:hover:not(:disabled) { box-shadow: 0 6px 16px rgba(116, 72, 20, .1); }
  .transfer-button--primary:hover:not(:disabled) { background: var(--color-action-hover); }
  .transfer-button--outline:hover:not(:disabled) { border-color: #c98748; background: #fff8ed; }
  .transfer-button--soft:hover:not(:disabled) { border-color: #c98748; background: #ffe8c2; }
  .quiet-button:hover { color: var(--color-action); background: var(--color-surface-warm); }
}

.migration-flow { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); align-items: stretch; gap: 20px; min-width: 0; }

.card { min-width: 0; }

.step-card {
  min-width: 0;
  padding: clamp(20px, 2.5vw, 26px);
  border-radius: 22px;
}

.config-card { display: grid; gap: 20px; }

.section-copy { min-width: 0; }
.section-copy h2, .tool-header h2 { margin: 8px 0 6px; color: var(--color-text); font-size: 21px; line-height: 1.25; text-wrap: balance; }
.section-copy p, .tool-header > div > p:last-child { max-width: 720px; margin: 0; color: var(--color-text-muted); font-size: 13px; line-height: 1.6; text-wrap: pretty; }

.panel-heading { display: flex; align-items: flex-start; gap: 14px; min-width: 0; }
.step-mark { display: grid; width: 48px; height: 48px; flex: 0 0 48px; place-items: center; border-radius: 15px; color: var(--color-action); background: var(--color-surface-accent); font-size: 16px; font-weight: 850; letter-spacing: .03em; }
.step-mark--muted { color: var(--color-text-muted); background: #f7f0e7; }
.panel-kicker { margin: 0; color: var(--color-accent); font-size: 11px; font-weight: 800; letter-spacing: .1em; }
.panel-format { display: inline-flex; min-height: 21px; align-items: center; border: 1px solid #edcfac; border-radius: 999px; padding: 0 8px; color: #93551e; background: var(--color-surface-accent); font-size: 10px; font-weight: 750; letter-spacing: .04em; }

.scope-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; min-width: 0; }
.scope-option { display: grid; grid-template-columns: auto minmax(0, 1fr); align-items: start; gap: 10px; min-width: 0; padding: 12px; border: 1px solid #f0dfc9; border-radius: 14px; background: #fffaf2; }
.scope-option--settings { background: #fffdf9; }
.scope-mark { display: inline-flex; min-height: 26px; align-items: center; border-radius: 8px; padding: 0 7px; color: var(--color-action); background: var(--color-surface-accent); font-size: 10px; font-weight: 850; letter-spacing: .04em; }
.scope-option strong { display: block; color: var(--color-text); font-size: 13px; line-height: 1.35; }
.scope-option p { margin: 3px 0 0; color: var(--color-text-muted); font-size: 11px; line-height: 1.45; overflow-wrap: anywhere; }

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
.file-type { display: inline-grid; width: 42px; height: 42px; flex: 0 0 42px; place-items: center; border: 1px solid #edcfac; border-radius: 11px; color: var(--color-action); background: #fff; font-size: 10px; font-weight: 850; letter-spacing: .04em; }
.file-copy { min-width: 0; }
.file-copy strong { display: block; overflow-wrap: anywhere; color: var(--color-text); font-size: 14px; line-height: 1.4; }
.file-copy p { margin: 4px 0 0; color: var(--color-text-muted); font-size: 12px; line-height: 1.45; overflow-wrap: anywhere; }

.question-import-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  min-width: 0;
}

.config-actions { display: flex; align-items: center; justify-content: space-between; gap: 16px; min-width: 0; flex-wrap: wrap; }
.primary-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; min-width: 0; }

.quiet-button { min-height: 40px; border: 0; border-radius: 10px; padding: 0 9px; color: var(--color-text-muted); background: transparent; font-size: 13px; font-weight: 650; }
.button-spinner { width: 13px; height: 13px; border: 2px solid rgba(255, 255, 255, .45); border-top-color: #fff; border-radius: 50%; animation: transfer-spin 700ms linear infinite; }
@keyframes transfer-spin { to { transform: rotate(360deg); } }

.settings-export {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  min-width: 0;
  color: var(--color-text-muted);
  text-align: right;
}

.settings-export > div { display: grid; gap: 3px; min-width: 0; }
.settings-export strong { color: var(--color-text); font-size: 12px; }
.settings-export span { font-size: 11px; line-height: 1.4; overflow-wrap: anywhere; }

.preview-card { display: grid; gap: 20px; }
.preview-card--empty { border-style: dashed; background: rgba(255, 255, 255, .72); }
.preview-content { display: grid; gap: 14px; min-width: 0; }

.preview-placeholder {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: center;
  gap: 16px;
  min-width: 0;
  min-height: 190px;
  margin: auto 0;
  padding: 18px;
  border: 1px dashed #e0c49e;
  border-radius: 14px;
  color: var(--color-text-muted);
  background: #fffbf5;
}

.placeholder-label {
  display: grid;
  width: 42px;
  height: 42px;
  place-items: center;
  border-radius: 9px;
  color: var(--color-text-muted);
  background: #f7f0e7;
  font-size: 12px;
  font-weight: 850;
}

.preview-placeholder strong { display: block; color: var(--color-text); font-size: 14px; }
.preview-placeholder p { margin: 5px 0 0; font-size: 12px; line-height: 1.6; text-wrap: pretty; }

.preview-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  min-width: 0;
  padding: 13px 14px;
  border: 1px solid #efdbc1;
  border-radius: 12px;
  background: #fffaf2;
}

.preview-banner > div { display: grid; gap: 7px; min-width: 0; }
.preview-mode { justify-self: start; min-height: 24px; padding: 0 9px; font-size: 11px; }
.preview-banner strong { color: var(--color-text); font-size: 14px; }
.preview-hint { color: var(--color-text-muted); font-size: 11px; white-space: nowrap; }

.hash-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; min-width: 0; }
.hash-item { display: grid; gap: 7px; min-width: 0; padding: 12px; border: 1px solid #f0dfc9; border-radius: 12px; background: #fff8ed; }
.hash-item > span { color: var(--color-text-muted); font-size: 11px; font-weight: 750; }
.hash-item code { min-width: 0; overflow-wrap: anywhere; color: var(--color-text); font-size: 11px; line-height: 1.5; }

.diff-table-wrap { width: 100%; min-width: 0; overflow-x: auto; border: 1px solid var(--color-border); border-radius: 12px; }
.diff-table { width: 100%; min-width: 500px; border-collapse: collapse; font-size: 12px; }
.diff-table th, .diff-table td { padding: 10px 12px; border-bottom: 1px solid var(--color-border); text-align: right; white-space: nowrap; }
.diff-table tr:last-child th, .diff-table tr:last-child td { border-bottom: 0; }
.diff-table th:first-child, .diff-table tbody th { text-align: left; }
.diff-table thead th { color: var(--color-text-muted); background: #fffaf2; font-size: 11px; font-weight: 750; }
.diff-table tbody th { color: var(--color-text); font-weight: 700; }

.warnings { margin: 0; padding: 11px 14px 11px 29px; border-radius: 10px; color: #805315; background: #fff3cf; font-size: 12px; line-height: 1.6; overflow-wrap: anywhere; }
.preview-footer { display: flex; align-items: stretch; justify-content: space-between; gap: 12px; min-width: 0; flex-wrap: wrap; }
.danger-note { display: grid; flex: 1 1 260px; gap: 4px; min-width: 0; padding: 12px 13px; border-left: 3px solid #d9794c; border-radius: 8px; color: #78412d; background: #fff0e8; font-size: 11px; line-height: 1.55; }
.danger-note strong { font-size: 12px; }.danger-note span { overflow-wrap: anywhere; }.confirm-button { align-self: center; margin-left: auto; }

.feedback,
.question-feedback {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  min-width: 0;
  padding: 13px 15px;
  border: 1px solid;
  border-radius: 12px;
  font-size: 13px;
  line-height: 1.55;
  overflow-wrap: anywhere;
}

.feedback { margin-top: 16px; }
.feedback--error, .question-feedback--error { color: #7d2f2a; border-color: #ecc3be; background: #fff0ee; }
.feedback--success, .question-feedback--success { color: #21602f; border-color: #c5e5cb; background: #edf8ef; }
.feedback-mark { display: inline-grid; width: 20px; height: 20px; flex: 0 0 20px; place-items: center; border-radius: 50%; color: #fff; font-size: 12px; font-weight: 850; }
.feedback--error .feedback-mark, .question-feedback--error .feedback-mark { background: #b5483f; }
.feedback--success .feedback-mark, .question-feedback--success .feedback-mark { background: #39864a; }

.question-bank-card { display: grid; gap: 18px; min-width: 0; margin-top: 24px; padding: clamp(20px, 2.5vw, 26px); }
.tool-header { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: start; gap: 18px; min-width: 0; }
.tool-header > div { min-width: 0; }
.card-kicker { margin: 0 0 8px; color: var(--color-accent); font-size: 11px; font-weight: 800; letter-spacing: .1em; }
.tool-badge { flex-shrink: 0; min-height: 28px; padding: 0 10px; font-size: 11px; white-space: nowrap; }

.question-tool-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; min-width: 0; }
.question-tool { display: flex; min-width: 0; flex-direction: column; gap: 18px; padding: 18px; border: 1px solid #f0dfc9; border-radius: 16px; background: #fffaf2; }
.question-tool--import { background: #fffdf9; }
.tool-heading { display: grid; grid-template-columns: minmax(48px, auto) minmax(0, 1fr); align-items: start; gap: 12px; min-width: 0; }
.tool-label { display: inline-flex; min-height: 26px; align-items: center; border-radius: 8px; padding: 0 8px; color: var(--color-action); background: var(--color-surface-accent); font-size: 11px; font-weight: 850; letter-spacing: .04em; }
.question-tool h3 { margin: 0 0 5px; color: var(--color-text); font-size: 17px; line-height: 1.3; }
.question-tool p { margin: 0; color: var(--color-text-muted); font-size: 12px; line-height: 1.6; text-wrap: pretty; }
.tool-footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-width: 0; margin-top: auto; padding-top: 2px; }
.tool-footer > span { color: var(--color-text-muted); font-size: 11px; overflow-wrap: anywhere; }
.question-file-picker { margin-top: auto; padding: 11px; border-radius: 12px; }
.question-file-picker .file-type { width: 36px; height: 36px; flex-basis: 36px; border-radius: 9px; }
.question-file-picker .file-copy strong { font-size: 13px; }
.question-file-picker .transfer-button { padding: 0 12px; }

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

code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }

@media (max-width: 1100px) {
  .migration-flow { grid-template-columns: 1fr; }
  .preview-placeholder { min-height: 140px; }
}

@media (max-width: 900px) {
  .admin-content { width: min(calc(100% - 32px), 720px); padding-top: 32px; }
  .page-header { grid-template-columns: 1fr; gap: 18px; }
  .export-all-button { width: 100%; }
  .question-tool-grid { grid-template-columns: 1fr; }
  .tool-header { grid-template-columns: 1fr; gap: 12px; }
  .tool-badge { justify-self: start; }
}

@media (max-width: 640px) {
  .admin-content { width: calc(100% - 32px); padding-bottom: 56px; }
  .step-card, .question-bank-card { padding: 18px; }
  .scope-grid { grid-template-columns: 1fr; }
  .file-picker { grid-template-columns: 1fr; align-items: stretch; }
  .file-picker .transfer-button, .primary-actions .transfer-button, .confirm-button { width: 100%; }
  .config-actions { align-items: stretch; flex-direction: column; }
  .primary-actions { align-items: stretch; flex-direction: column; }
  .quiet-button { align-self: flex-start; }
  .settings-export { align-items: stretch; justify-content: space-between; width: 100%; margin-left: 0; padding-top: 14px; border-top: 1px solid var(--color-border); text-align: left; }
  .settings-export .transfer-button { flex-shrink: 1; }
  .preview-placeholder { grid-template-columns: 1fr; align-items: start; }
  .preview-banner { align-items: flex-start; flex-direction: column; }
  .preview-hint { white-space: normal; }
  .hash-grid { grid-template-columns: 1fr; }
  .preview-footer { align-items: stretch; flex-direction: column; }
  .confirm-button { margin-left: 0; }
  .question-tool { padding: 16px; }
  .tool-footer { align-items: stretch; flex-direction: column; }
  .tool-footer .transfer-button, .question-import-actions .transfer-button { width: 100%; }
  .question-import-actions { align-items: stretch; flex-direction: column; }
  .question-import-actions .quiet-button { align-self: flex-start; }
  .question-result-heading { align-items: flex-start; flex-direction: column; gap: 6px; }
}

@media (max-width: 420px) {
  .admin-content { width: calc(100% - 24px); }
  .panel-heading { gap: 11px; }
  .step-mark { width: 42px; height: 42px; flex-basis: 42px; border-radius: 13px; font-size: 14px; }
  .section-copy h2 { font-size: 19px; }
  .settings-export { align-items: flex-start; flex-direction: column; }
  .settings-export .transfer-button { width: 100%; }
  .tool-heading { grid-template-columns: 1fr; gap: 9px; }
  .tool-label { justify-self: start; }
}

@media (prefers-reduced-motion: reduce) {
  .button-spinner { animation: none; }
  .transfer-button { transition: none; }
}
</style>
