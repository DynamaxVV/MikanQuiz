<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router';
import { ElInput, ElMessage, ElRadioButton, ElRadioGroup } from 'element-plus';
import { api, ApiError } from '@/api/client';
import AdminShell from '@/components/AdminShell.vue';
import ErrorPanel from '@/components/ErrorPanel.vue';
import QuestionMedia from '@/components/QuestionMedia.vue';
import type { AnswerKey, Question, QuestionPayload } from '@/types';

const route = useRoute();
const router = useRouter();
const questionId = computed(() => typeof route.params.id === 'string' ? route.params.id : '');
const isEditing = computed(() => Boolean(questionId.value));
const defaultText = '请选择以下日文对应的汉字字体';
const form = reactive<QuestionPayload>({ text: defaultText, imageUrl: null, difficulty: 3, options: { A: '', B: '', C: '', D: '' }, answer: 'A', explanation: '' });
const fontPresets = ref<string[]>([]);
const activeOption = ref<AnswerKey>('A');
const loading = ref(isEditing.value);
const saving = ref(false);
const error = ref('');
const success = ref('');
const initial = ref('');
const imageUrlInput = ref('');
const imageUploading = ref(false);
const optionKeys: AnswerKey[] = ['A', 'B', 'C', 'D'];
const dirty = computed(() => snapshot() !== initial.value);
type FieldName = 'text' | 'difficulty' | 'imageUrl' | 'optionA' | 'optionB' | 'optionC' | 'optionD' | 'answer' | 'explanation';
const fieldErrors = reactive<Record<FieldName, string>>({ text: '', difficulty: '', imageUrl: '', optionA: '', optionB: '', optionC: '', optionD: '', answer: '', explanation: '' });

function snapshot(): string {
  return JSON.stringify({ ...form, imageUrl: imageUrlInput.value.trim() || null });
}

function assignQuestion(question: Question): void {
  form.text = question.text;
  form.imageUrl = question.imageUrl;
  imageUrlInput.value = question.imageUrl ?? '';
  form.difficulty = question.difficulty;
  form.options = { ...question.options };
  form.answer = question.answer ?? 'A';
  form.explanation = question.explanation ?? '';
}

async function load(): Promise<void> {
  loading.value = true;
  error.value = '';
  try {
    const [settings, question] = await Promise.all([api.getAdminSettings(), isEditing.value ? api.getQuestion(questionId.value) : Promise.resolve(null)]);
    fontPresets.value = settings.fontPresets;
    if (question) assignQuestion(question);
    initial.value = snapshot();
  } catch (caught) { error.value = caught instanceof Error ? caught.message : '题目编辑器加载失败。'; }
  finally { loading.value = false; }
}

function clearFieldErrors(): void {
  (Object.keys(fieldErrors) as FieldName[]).forEach((field) => { fieldErrors[field] = ''; });
}

function setFieldError(field: FieldName, message: string): void {
  fieldErrors[field] = message;
}

function hasFieldErrors(): boolean {
  return Object.values(fieldErrors).some(Boolean);
}

function isHttpsUrl(value: string): boolean {
  try { return new URL(value).protocol === 'https:' && Boolean(new URL(value).hostname); }
  catch { return false; }
}

function validate(): boolean {
  clearFieldErrors();
  form.imageUrl = imageUrlInput.value.trim() || null;
  if (!form.text.trim()) setFieldError('text', '请填写题干。');
  else if (form.text.trim().length > 500) setFieldError('text', '题干不能超过 500 字。');
  if (!Number.isInteger(Number(form.difficulty)) || form.difficulty < 1 || form.difficulty > 5) setFieldError('difficulty', '请选择 1 到 5 星难度。');
  if (form.imageUrl && !isHttpsUrl(form.imageUrl)) setFieldError('imageUrl', '图片 URL 必须使用有效的 HTTPS 地址。');
  optionKeys.forEach((key) => {
    const field = `option${key}` as FieldName;
    if (!form.options[key].trim()) setFieldError(field, `请填写选项 ${key}。`);
    else if (form.options[key].trim().length > 500) setFieldError(field, `选项 ${key} 不能超过 500 字。`);
  });
  if (!optionKeys.includes(form.answer)) setFieldError('answer', '请选择正确答案。');
  if (!form.explanation.trim()) setFieldError('explanation', '请填写题目解析。');
  else if (form.explanation.trim().length > 1000) setFieldError('explanation', '题目解析不能超过 1000 字。');
  return !hasFieldErrors();
}

function mapServerValidation(caught: unknown): boolean {
  if (!(caught instanceof ApiError) || caught.status !== 422) return false;
  const message = caught.message;
  if (message.includes('图片')) setFieldError('imageUrl', message);
  if (message.includes('选项')) optionKeys.forEach((key) => setFieldError(`option${key}` as FieldName, message));
  if (message.includes('题干')) setFieldError('text', message);
  if (message.includes('解析')) setFieldError('explanation', message);
  if (message.includes('答案')) setFieldError('answer', message);
  return hasFieldErrors();
}

function payload(): QuestionPayload {
  return { text: form.text.trim(), imageUrl: form.imageUrl, difficulty: Number(form.difficulty), options: Object.fromEntries(optionKeys.map((key) => [key, form.options[key].trim()])) as QuestionPayload['options'], answer: form.answer, explanation: form.explanation.trim() };
}

function insertPreset(preset: string): void {
  form.options[activeOption.value] = preset;
  void nextTick(() => document.querySelector<HTMLInputElement>(`[data-option-input="${activeOption.value}"] input`)?.focus());
}

async function save(): Promise<void> {
  if (saving.value) return;
  error.value = '';
  success.value = '';
  if (!validate()) { error.value = '请检查标红的字段后再保存。'; return; }
  saving.value = true;
  try {
    const saved = isEditing.value ? await api.updateQuestion(questionId.value, payload()) : await api.createQuestion(payload());
    initial.value = snapshot();
    success.value = isEditing.value ? '题目已保存。' : '题目已加入题库。';
    ElMessage.success(success.value);
    if (!isEditing.value) await router.replace(`/admin/questions/${encodeURIComponent(saved.id)}/edit`);
  } catch (caught) {
    const mapped = mapServerValidation(caught);
    error.value = mapped ? '服务端校验未通过，请检查标红的字段。' : caught instanceof Error ? caught.message : '保存失败，请检查字段后重试。';
  }
  finally { saving.value = false; }
}

async function uploadImage(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file || imageUploading.value) return;
  imageUploading.value = true;
  error.value = '';
  try {
    imageUrlInput.value = await api.uploadImage(file);
    clearFieldErrors();
    ElMessage.success('图片已上传，可继续编辑题目。');
  } catch (caught) { error.value = caught instanceof Error ? caught.message : '图片上传失败，请稍后重试。'; }
  finally { imageUploading.value = false; input.value = ''; }
}

function onKeydown(event: KeyboardEvent): void {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 's') { event.preventDefault(); void save(); }
}

onMounted(() => { void load(); window.addEventListener('keydown', onKeydown); });
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown));
onBeforeRouteLeave(() => !dirty.value || saving.value || window.confirm('还有未保存的修改。确定离开编辑页面吗？'));
watch(imageUrlInput, (value) => { form.imageUrl = value.trim() || null; });
</script>

<template>
  <AdminShell>
    <section class="admin-content">
      <header class="page-header">
        <div><p class="eyebrow">题库</p><h1 class="page-title">{{ isEditing ? '编辑题目' : '新增题目' }}</h1><p class="page-description">左侧录入内容，右侧会按答题端的方式实时预览。</p></div>
        <RouterLink class="back-link" to="/admin/questions">返回题库</RouterLink>
      </header>
      <div v-if="loading" class="loading card">正在准备题目编辑器…</div>
      <ErrorPanel v-else-if="error && !initial" :message="error" @retry="load" />
      <div v-else class="editor-layout">
        <form class="question-form card" @submit.prevent="save">
          <div class="field" :class="{ 'has-error': fieldErrors.text }"><label for="question-text">题干</label><el-input id="question-text" v-model="form.text" type="textarea" :rows="3" maxlength="500" show-word-limit :aria-invalid="Boolean(fieldErrors.text)" aria-describedby="question-text-error" /><p v-if="fieldErrors.text" id="question-text-error" class="field-error">{{ fieldErrors.text }}</p></div>
          <fieldset class="field star-field" :class="{ 'has-error': fieldErrors.difficulty }"><legend>难度</legend><div class="star-picker" aria-describedby="difficulty-error"><label v-for="star in 5" :key="star" :class="{ selected: star <= form.difficulty }"><input v-model="form.difficulty" type="radio" name="difficulty" :value="star" /><span aria-hidden="true">⭐️</span><span class="sr-only">{{ star }} 星难度</span></label></div><p v-if="fieldErrors.difficulty" id="difficulty-error" class="field-error">{{ fieldErrors.difficulty }}</p></fieldset>
          <div class="field" :class="{ 'has-error': fieldErrors.imageUrl }"><label for="image-upload">题图</label><input id="image-upload" accept="image/jpeg,image/png,image/gif,image/webp" type="file" @change="uploadImage" /><small v-if="imageUploading">正在上传图片…</small><p v-if="fieldErrors.imageUrl" id="image-url-error" class="field-error">{{ fieldErrors.imageUrl }}</p></div>
          <fieldset class="options-field"><legend>选项</legend><div v-for="key in optionKeys" :key="key" class="option-input" :class="{ 'has-error': fieldErrors[`option${key}` as FieldName] }"><span>{{ key }}</span><div><el-input :data-option-input="key" v-model="form.options[key]" :placeholder="`选项 ${key}`" :aria-invalid="Boolean(fieldErrors[`option${key}` as FieldName])" :aria-describedby="`option-${key}-error`" @focus="activeOption = key" /><p v-if="fieldErrors[`option${key}` as FieldName]" :id="`option-${key}-error`" class="field-error">{{ fieldErrors[`option${key}` as FieldName] }}</p></div></div><div v-if="fontPresets.length" class="preset-row"><span>字体快捷项</span><button v-for="preset in fontPresets" :key="preset" type="button" @click="insertPreset(preset)">{{ preset }}</button></div></fieldset>
          <div class="field" :class="{ 'has-error': fieldErrors.answer }"><span>正确答案</span><el-radio-group v-model="form.answer" :aria-invalid="Boolean(fieldErrors.answer)" aria-describedby="answer-error"><el-radio-button v-for="key in optionKeys" :key="key" :value="key">{{ key }}</el-radio-button></el-radio-group><p v-if="fieldErrors.answer" id="answer-error" class="field-error">{{ fieldErrors.answer }}</p></div>
          <div class="field" :class="{ 'has-error': fieldErrors.explanation }"><label for="explanation">题目解析</label><el-input id="explanation" v-model="form.explanation" type="textarea" :rows="5" maxlength="1000" show-word-limit :aria-invalid="Boolean(fieldErrors.explanation)" aria-describedby="explanation-error" /><p v-if="fieldErrors.explanation" id="explanation-error" class="field-error">{{ fieldErrors.explanation }}</p></div>
          <p v-if="error" class="status-error" role="alert">{{ error }}</p><p v-if="success" class="status-success" role="status">{{ success }}</p><button class="save" type="submit" :disabled="saving">{{ saving ? '正在保存…' : '保存题目' }}</button><p class="save-hint">按 Cmd/Ctrl + S 可保存。</p>
        </form>
        <aside class="preview"><p class="preview-label">答题端预览</p><section class="preview-card card"><p class="eyebrow">第 1 题 · {{ '★'.repeat(form.difficulty) }}</p><h2>{{ form.text || '题干会显示在这里' }}</h2><QuestionMedia :image-url="form.imageUrl" :text="form.text || '题目'" /><div class="preview-options"><div v-for="key in optionKeys" :key="key" :class="{ correct: key === form.answer }"><strong>{{ key }}</strong><span>{{ form.options[key] || `选项 ${key}` }}</span><em v-if="key === form.answer">正确答案</em></div></div></section></aside>
      </div>
    </section>
  </AdminShell>
</template>

<style scoped>
.admin-content { width: min(1440px, calc(100% - 64px)); margin: 0 auto; padding: 48px 0 64px; }.page-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; margin-bottom: 24px; }.page-description { margin-bottom: 0; }.back-link { min-height: 40px; display: grid; place-items: center; padding: 0 12px; border: 1px solid var(--color-border); border-radius: 10px; color: var(--color-action); font-weight: 700; }.loading { padding: 32px; color: var(--color-text-muted); }.editor-layout { display: grid; grid-template-columns: minmax(0, 7fr) minmax(340px, 5fr); gap: 24px; }.question-form { display: grid; gap: 22px; padding: 28px; }.field, .options-field { display: grid; gap: 9px; padding: 0; border: 0; }.field > label, .field > span, .options-field legend { color: var(--color-text); font-size: 14px; font-weight: 750; }.field small { color: var(--color-text-muted); font-size: 13px; line-height: 1.5; }.field-error { margin: 0; color: var(--color-danger); font-size: 13px; font-weight: 650; line-height: 1.45; }.has-error :deep(.el-input__wrapper), .has-error :deep(.el-textarea__inner), .has-error :deep(.el-radio-button__inner) { border-color: var(--color-danger); box-shadow: 0 0 0 1px var(--color-danger) inset; }.options-field { gap: 10px; }.option-input { display: grid; grid-template-columns: 30px 1fr; align-items: start; gap: 10px; }.option-input > span { display: grid; width: 30px; height: 30px; place-items: center; border: 1px solid var(--color-border); border-radius: 50%; color: var(--color-text-muted); font-size: 13px; font-weight: 700; }.option-input.has-error > span { border-color: var(--color-danger); color: var(--color-danger); }.preset-row { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-top: 5px; }.preset-row > span { margin-right: 4px; color: var(--color-text-muted); font-size: 13px; }.preset-row button { min-height: 30px; border: 1px solid #edcfac; border-radius: 999px; padding: 0 10px; color: #8d4a20; background: var(--color-surface-accent); }.save { min-height: 48px; border: 0; border-radius: var(--radius-button); color: #fff; background: var(--color-action); font-weight: 750; }.save:hover { background: var(--color-action-hover); }.save:disabled { opacity: .65; }.save-hint { margin: -12px 0 0; color: var(--color-text-muted); font-size: 13px; }.preview { position: sticky; top: 20px; align-self: start; }.preview-label { margin: 0 0 8px; color: var(--color-text-muted); font-size: 13px; font-weight: 750; }.preview-card { padding: 22px; }.preview-card h2 { margin: 0 0 18px; font-size: 22px; line-height: 1.35; }.preview-options { display: grid; gap: 8px; margin-top: 14px; }.preview-options > div { display: grid; grid-template-columns: 28px 1fr auto; gap: 9px; align-items: center; min-height: 44px; padding: 8px; border: 1px solid var(--color-border); border-radius: 10px; background: var(--color-surface-warm); }.preview-options .correct { border-color: #82b78c; background: #edf8ef; }.preview-options strong { display: grid; width: 25px; height: 25px; place-items: center; border: 1px solid currentColor; border-radius: 50%; color: var(--color-text-muted); font-size: 12px; }.preview-options em { color: var(--color-success); font-size: 12px; font-style: normal; font-weight: 700; }
@media (max-width: 1023px) { .admin-content { width: min(100% - 32px, 1440px); padding-top: 28px; }.editor-layout { grid-template-columns: 1fr; }.preview { position: static; }.question-form { padding: 22px; } }.page-header { flex-wrap: wrap; }
.star-field legend { color: var(--color-text); font-size: 14px; font-weight: 750; }.star-picker { display: flex; gap: 7px; }.star-picker label { cursor: pointer; font-size: 26px; line-height: 1; filter: grayscale(1) opacity(.24); }.star-picker label.selected { filter: none; }.star-picker input { position: absolute; opacity: 0; pointer-events: none; }.star-picker label:has(input:focus-visible) { outline: 2px solid var(--color-focus); outline-offset: 3px; border-radius: 5px; }
</style>
