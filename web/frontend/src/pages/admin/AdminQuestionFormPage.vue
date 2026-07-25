<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue';
import { useRoute } from 'vue-router';
import { ElMessage } from 'element-plus';
import { api } from '@/api/client';
import { useFontRendering } from '@/composables/useFontRendering';
import AdminShell from '@/components/AdminShell.vue';
import ErrorPanel from '@/components/ErrorPanel.vue';
import type { OptionGroup, QuestionPayload } from '@/types';

const route = useRoute();
const { fontStyle } = useFontRendering();
const fontRenderEnabled = ref(true);
const id = computed(() => String(route.params.id || ''));
const editing = computed(() => Boolean(id.value));
const groups = ref<OptionGroup[]>([]);
const loading = ref(true);
const saving = ref(false);
const pendingImageFile = ref<File | null>(null);
const fileInputRef = ref<HTMLInputElement | null>(null);
const error = ref('');

const previewUrl = computed(() => {
  if (pendingImageFile.value) return URL.createObjectURL(pendingImageFile.value);
  return form.imageUrl;
});

function resetForm(): void {
  if (previewUrl.value?.startsWith('blob:')) URL.revokeObjectURL(previewUrl.value);
  pendingImageFile.value = null;
  form.text = '请选择以下日文对应的汉字字体';
  form.imageUrl = null;
  form.difficulty = 2;
  form.correctOptionId = '';
  form.explanation = '';
  error.value = '';
}

function setLocalImage(file: File): void {
  if (previewUrl.value?.startsWith('blob:')) URL.revokeObjectURL(previewUrl.value);
  pendingImageFile.value = file;
}

const form = reactive<QuestionPayload>({ text: '请选择以下日文对应的汉字字体', imageUrl: null, difficulty: 2, correctOptionId: '', explanation: '' });
const visibleGroups = computed(() => groups.value.map((group) => ({ ...group, options: group.options.filter((option) => option.minimumDifficulty <= form.difficulty) })).filter((group) => group.options.length));

async function load(): Promise<void> {
  loading.value = true;
  error.value = '';
  try {
    const [catalog, question] = await Promise.all([api.getOptionGroups(), editing.value ? api.getQuestion(id.value) : Promise.resolve(null)]);
    groups.value = catalog;
    if (question) Object.assign(form, { text: question.text, imageUrl: question.imageUrl, difficulty: question.difficulty, correctOptionId: question.correctOptionId || '', explanation: question.explanation || '' });
  } catch (caught) { error.value = caught instanceof Error ? caught.message : '题目编辑器加载失败。'; }
  finally { loading.value = false; }
}

async function uploadImage(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  setLocalImage(file);
  input.value = '';
}

const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];

function onPaste(event: ClipboardEvent): void {
  const items = event.clipboardData?.items;
  if (!items || saving.value) return;
  for (const item of items) {
    if (item.type.startsWith('image/')) {
      const blob = item.getAsFile();
      if (!blob) continue;
      if (!ACCEPTED_TYPES.includes(blob.type)) {
        error.value = '仅支持 JPEG、PNG、GIF、WebP 格式的图片';
        continue;
      }
      event.preventDefault();
      const ext = blob.type.split('/')[1] || 'png';
      setLocalImage(new File([blob], `clipboard.${ext}`, { type: blob.type }));
      return;
    }
  }
}

function triggerFileInput(): void {
  fileInputRef.value?.click();
}

async function save(): Promise<void> {
  if (!form.text.trim() || !previewUrl.value || !form.correctOptionId || !form.explanation.trim()) {
    error.value = '请填写题干、上传题图、选择正确字体并填写解析。';
    return;
  }
  saving.value = true;
  error.value = '';
  try {
    let imageUrl = form.imageUrl;
    if (pendingImageFile.value) {
      imageUrl = await api.uploadImage(pendingImageFile.value);
    }
    if (!imageUrl) throw new Error('请上传题图');
    const payload = { ...form, imageUrl };
    if (editing.value) await api.updateQuestion(id.value, payload);
    else await api.createQuestion(payload);
    ElMessage.success('题目已保存。');
    if (editing.value) {
      await load();
    } else {
      resetForm();
    }
  } catch (caught) { error.value = caught instanceof Error ? caught.message : '保存失败。'; }
  finally { saving.value = false; }
}

onMounted(() => { void load(); document.addEventListener('paste', onPaste); });
onBeforeUnmount(() => { document.removeEventListener('paste', onPaste); });
</script>

<template>
  <AdminShell><section class="admin-content"><header class="page-header"><p class="eyebrow">题库</p><h1 class="page-title">{{ editing ? '编辑题目' : '新增题目' }}</h1><p class="page-description">选择正确字体后，答题端会按本题星级展示相应分区中的全部可选字体。</p></header><div v-if="loading" class="loading card">正在准备题目编辑器…</div><ErrorPanel v-else-if="error && !groups.length" :message="error" @retry="load" /><form v-else class="editor" :class="{ saving }" @submit.prevent="save"><div class="form-column"><section class="card"><div class="section-heading"><span>01</span><div><h2>题目内容</h2><p>填写一行题干、难度与题图。</p></div></div><label class="field">题干<input v-model="form.text" maxlength="500" placeholder="请输入题干" /></label><div class="two-fields"><div class="field">题目难度<div class="star-picker" aria-label="选择题目难度"><button v-for="star in 3" :key="star" type="button" :class="{ active: star <= form.difficulty }" :aria-label="`${star} 星`" @click="form.difficulty = star">★</button></div></div><div class="upload-zone" tabindex="0" role="button" :class="{ saving }" :aria-label="'点击选择或粘贴图片'" @click="triggerFileInput" @keydown.enter.prevent="triggerFileInput" @keydown.space.prevent="triggerFileInput">
  <input ref="fileInputRef" accept="image/jpeg,image/png,image/gif,image/webp" type="file" :disabled="saving" @change="uploadImage" hidden />
  <template v-if="previewUrl">
    <img :src="previewUrl" alt="题图预览" />
    <small>{{ pendingImageFile ? '待上传，保存后将提交到服务器' : '已上传，点击或粘贴重新选择' }}</small>
  </template>
  <template v-else>
    <svg class="upload-icon" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
    <span>点击选择图片 或 Ctrl+V 粘贴</span>
    <small>支持 JPEG、PNG、GIF、WebP</small>
  </template>
</div></div></section><section class="card"><div class="section-heading"><span>02</span><div><h2>正确字体</h2><p>只需选择正确项，候选项由字体快捷项统一维护。</p></div></div><div class="group-grid"><section v-for="group in visibleGroups" :key="group.id" class="answer-group"><h3>{{ group.name }}</h3><label v-for="option in group.options" :key="option.id" class="option" :class="{ selected: form.correctOptionId === option.id }"><input v-model="form.correctOptionId" type="radio" :value="option.id" /><span>{{ option.name }}</span></label></section></div></section><section class="card"><div class="section-heading"><span>03</span><div><h2>题目解析</h2><p>提交后会展示给答题者。</p></div></div><label class="field"><textarea v-model="form.explanation" maxlength="1000" placeholder="写下判别依据或补充说明" /></label></section></div><aside class="preview"><p class="preview-label">答题端预览</p><label class="font-render-toggle">
    <span class="toggle-label">即时渲染字体</span>
    <span class="toggle-track" :class="{ on: fontRenderEnabled }" @click.prevent="fontRenderEnabled = !fontRenderEnabled" role="switch" :aria-checked="fontRenderEnabled" tabindex="0"><span class="toggle-thumb"></span></span>
  </label><section class="preview-card card"><p class="eyebrow">第 1 题 · {{ '★'.repeat(form.difficulty) }}</p><h2>{{ form.text || '题干会显示在这里' }}</h2><img v-if="previewUrl" :src="previewUrl" alt="题图预览" /><div v-for="group in visibleGroups" :key="group.id" class="preview-group"><h3>{{ group.name }}</h3><span v-for="option in group.options" :key="option.id" :style="fontRenderEnabled ? fontStyle(option) : undefined" :class="{ correct: form.correctOptionId === option.id }">{{ option.name }}</span></div></section></aside><p v-if="error" class="status-error" role="alert">{{ error }}</p><footer class="save-bar"><p>保存后，题目会立即使用当前字体分区规则。</p><button :disabled="saving" class="save-button">
  <span v-if="saving" class="loading-spinner"></span>
  {{ saving ? '正在保存…' : '保存题目' }}
</button></footer></form></section></AdminShell>
</template>

<style scoped>
.editor aside.preview { position: static !important; }
.editor.saving { opacity: .7; pointer-events: none; }
.editor.saving .save-bar { pointer-events: auto; }
.preview-card > img { height: 210px; max-height: none; object-fit: contain !important; background: var(--color-surface-warm); }
.admin-content { width: min(1120px, calc(100% - 64px)); margin: auto; padding: 48px 0 64px; }.page-header { margin-bottom: 28px; }.page-description { max-width: 610px; margin-bottom: 0; }.loading, .card { padding: 24px; }.editor { display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: 16px; }.form-column { display: grid; gap: 14px; }.section-heading { display: flex; gap: 12px; align-items: flex-start; margin-bottom: 16px; }.section-heading > span { display: grid; width: 30px; height: 30px; place-items: center; border-radius: 50%; color: #93551e; background: #fff0d8; font-size: 12px; font-weight: 800; }.section-heading h2, .preview-card h2 { margin: 0; font-size: 18px; }.section-heading p, .field small { margin: 4px 0 0; color: var(--color-text-muted); font-size: 13px; }.field { display: grid; gap: 7px; color: var(--color-text-muted); font-size: 13px; font-weight: 750; }.two-fields { display: grid; grid-template-columns: 180px minmax(0, 1fr); gap: 14px; margin-top: 14px; }.field input, .field textarea { width: 100%; border: 1px solid var(--color-border); border-radius: var(--radius-input); padding: 9px 11px; color: var(--color-text); background: var(--color-surface-warm); font: inherit; }.upload-field { padding: 11px; border: 1px solid #efdbc1; border-radius: 12px; background: #fff8ed; }.upload-field input[type=file] { padding: 6px 0; background: transparent; }
.upload-zone { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; min-height: 140px; border: 2px dashed #dcc6ae; border-radius: 12px; padding: 16px; cursor: pointer; color: var(--color-text-muted); font-size: 13px; font-weight: 600; background: #fff8ed; transition: border-color 150ms, background 150ms; outline: none; }
.upload-zone:hover { border-color: #c4a888; background: #fff3e0; }
.upload-zone:focus-visible { border-color: var(--color-action); box-shadow: 0 0 0 3px rgba(169, 79, 31, .15); }
.upload-zone .upload-icon { opacity: .6; }
.upload-zone img { width: 100%; max-height: 160px; object-fit: contain; border-radius: 8px; }
.upload-zone.saving { opacity: .55; pointer-events: none; }
.upload-zone small { font-weight: 400; }.field textarea { min-height: 96px; resize: vertical; }
.loading-spinner { display: inline-block; width: 14px; height: 14px; border: 2px solid rgba(255,255,255,.3); border-top-color: #fff; border-radius: 50%; animation: spin .6s linear infinite; margin-right: 6px; } @keyframes spin { to { transform: rotate(360deg); } }
.save-button { display: inline-flex; align-items: center; }.star-picker { display: flex; gap: 6px; }.star-picker button { border: 0; padding: 0; background: transparent; color: #dfd2c4; font-size: 30px; line-height: 1; cursor: pointer; }.star-picker button.active { color: #ff9800; }.image-preview { display: flex; align-items: center; gap: 14px; margin-top: 14px; padding: 10px; border: 1px solid #efdbc1; border-radius: 12px; background: #fff8ed; }.image-preview img { width: 120px; height: 84px; object-fit: cover; border-radius: 8px; }.image-preview div { display: grid; gap: 8px; font-size: 13px; }.image-preview button { justify-self: start; min-height: 30px; border: 1px solid #edcfac; border-radius: 8px; padding: 0 9px; color: #93551e; background: #fff; }.group-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }.answer-group { padding: 10px; border: 1px solid var(--color-border); border-radius: 12px; background: #fffdf9; }.answer-group h3, .preview-group h3 { margin: 0 0 5px; color: #85451e; font-size: 12px; }.option, .preview-group span { display: inline-flex; align-items: center; gap: 5px; margin: 0 4px 4px 0; border: 1px solid transparent; border-radius: 10px; padding: 0 6px; height: 34px; line-height: 1.2; color: var(--color-text-muted); background: var(--color-surface-warm); font-size: 12px; cursor: pointer; }.option input { width: auto; margin: 0; }.option.selected, .preview-group .correct { border-color: #d58a45; color: #85451e; background: #fff0d8; }.preview { align-self: start; position: sticky; top: 20px; }.preview-label { margin: 0 0 8px; color: var(--color-text-muted); font-size: 13px; font-weight: 750; }.font-render-toggle { display: flex; align-items: center; justify-content: flex-end; gap: 8px; margin-bottom: 8px; cursor: pointer; user-select: none; }.toggle-label { color: var(--color-text-muted); font-size: 12px; font-weight: 650; }.toggle-track { position: relative; width: 44px; height: 26px; border-radius: 999px; background: #e3d7c7; cursor: pointer; transition: background 160ms ease-out; outline: none; }.toggle-track.on { background: var(--color-action); }.toggle-thumb { position: absolute; top: 3px; left: 3px; width: 20px; height: 20px; border-radius: 50%; background: #fff; box-shadow: 0 1px 3px rgba(73, 48, 26, 0.16); transition: transform 180ms ease-out; }.toggle-track.on .toggle-thumb { transform: translateX(18px); }.preview-card { background: #fffdf9; }.preview-card > img { width: 100%; max-height: 210px; object-fit: cover; border-radius: 10px; margin: 14px 0; }.preview-group { margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--color-border); }.save-bar { grid-column: 1 / -1; display: flex; align-items: center; justify-content: space-between; gap: 20px; padding: 16px 20px; border: 1px solid #efdbc1; border-radius: 14px; background: #fff8ed; }.save-bar p { margin: 0; color: var(--color-text-muted); font-size: 13px; }.save-bar button { min-height: 44px; border: 0; border-radius: var(--radius-button); padding: 0 20px; color: #fff; background: var(--color-action); font-weight: 750; }.save-bar button:disabled { opacity: .65; }
@media (max-width: 900px) { .admin-content { width: min(100% - 32px, 1120px); padding-top: 28px; }.editor { grid-template-columns: 1fr; }.preview { position: static; }.save-bar { grid-column: auto; } } @media (max-width: 600px) { .save-bar { flex-direction: column; }.two-fields, .group-grid { grid-template-columns: 1fr; }.save-bar button { width: 100%; } }
</style>
