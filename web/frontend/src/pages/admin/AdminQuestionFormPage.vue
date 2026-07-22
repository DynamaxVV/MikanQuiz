<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { useRoute } from 'vue-router';
import { ElMessage } from 'element-plus';
import { api } from '@/api/client';
import AdminShell from '@/components/AdminShell.vue';
import ErrorPanel from '@/components/ErrorPanel.vue';
import type { OptionGroup, QuestionPayload } from '@/types';

const route = useRoute();
const id = computed(() => String(route.params.id || ''));
const editing = computed(() => Boolean(id.value));
const groups = ref<OptionGroup[]>([]);
const loading = ref(true);
const saving = ref(false);
const imageUploading = ref(false);
const error = ref('');
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
  imageUploading.value = true;
  error.value = '';
  try { form.imageUrl = await api.uploadImage(file); ElMessage.success('题图上传成功'); }
  catch (caught) { error.value = caught instanceof Error ? caught.message : '题图上传失败。'; }
  finally { imageUploading.value = false; input.value = ''; }
}

async function save(): Promise<void> {
  if (!form.text.trim() || !form.imageUrl || !form.correctOptionId || !form.explanation.trim()) {
    error.value = '请填写题干、上传题图、选择正确字体并填写解析。';
    return;
  }
  saving.value = true;
  error.value = '';
  try {
    if (editing.value) await api.updateQuestion(id.value, form);
    else await api.createQuestion(form);
    ElMessage.success('题目已保存。');
  } catch (caught) { error.value = caught instanceof Error ? caught.message : '保存失败。'; }
  finally { saving.value = false; }
}

onMounted(() => { void load(); });
</script>

<template>
  <AdminShell><section class="admin-content"><header class="page-header"><p class="eyebrow">题库</p><h1 class="page-title">{{ editing ? '编辑题目' : '新增题目' }}</h1><p class="page-description">选择正确字体后，答题端会按本题星级展示相应分区中的全部可选字体。</p></header><div v-if="loading" class="loading card">正在准备题目编辑器…</div><ErrorPanel v-else-if="error && !groups.length" :message="error" @retry="load" /><form v-else class="editor" @submit.prevent="save"><div class="form-column"><section class="card"><div class="section-heading"><span>01</span><div><h2>题目内容</h2><p>填写一行题干、难度与题图。</p></div></div><label class="field">题干<input v-model="form.text" maxlength="500" placeholder="请输入题干" /></label><div class="two-fields"><div class="field">题目难度<div class="star-picker" aria-label="选择题目难度"><button v-for="star in 3" :key="star" type="button" :class="{ active: star <= form.difficulty }" :aria-label="`${star} 星`" @click="form.difficulty = star">★</button></div></div><label class="field upload-field">题图<input accept="image/jpeg,image/png,image/gif,image/webp" type="file" :disabled="imageUploading" @change="uploadImage" /><small>{{ imageUploading ? '正在上传…' : form.imageUrl ? '已上传，可重新选择图片' : '支持 JPEG、PNG、GIF、WebP' }}</small></label></div></section><section class="card"><div class="section-heading"><span>02</span><div><h2>正确字体</h2><p>只需选择正确项，候选项由字体快捷项统一维护。</p></div></div><div class="group-grid"><section v-for="group in visibleGroups" :key="group.id" class="answer-group"><h3>{{ group.name }}</h3><label v-for="option in group.options" :key="option.id" class="option" :class="{ selected: form.correctOptionId === option.id }"><input v-model="form.correctOptionId" type="radio" :value="option.id" /><span>{{ option.name }}</span></label></section></div></section><section class="card"><div class="section-heading"><span>03</span><div><h2>题目解析</h2><p>提交后会展示给答题者。</p></div></div><label class="field"><textarea v-model="form.explanation" maxlength="1000" placeholder="写下判别依据或补充说明" /></label></section></div><aside class="preview"><p class="preview-label">答题端预览</p><section class="preview-card card"><p class="eyebrow">第 1 题 · {{ '★'.repeat(form.difficulty) }}</p><h2>{{ form.text || '题干会显示在这里' }}</h2><img v-if="form.imageUrl" :src="form.imageUrl" alt="题图预览" /><div v-for="group in visibleGroups" :key="group.id" class="preview-group"><h3>{{ group.name }}</h3><span v-for="option in group.options" :key="option.id" :class="{ correct: form.correctOptionId === option.id }">{{ option.name }}</span></div></section></aside><p v-if="error" class="status-error" role="alert">{{ error }}</p><footer class="save-bar"><p>保存后，题目会立即使用当前字体分区规则。</p><button :disabled="saving">{{ saving ? '正在保存…' : '保存题目' }}</button></footer></form></section></AdminShell>
</template>

<style scoped>
.editor aside.preview { position: static !important; }
.preview-card > img { height: 210px; max-height: none; object-fit: contain !important; background: var(--color-surface-warm); }
.admin-content { width: min(1120px, calc(100% - 64px)); margin: auto; padding: 48px 0 64px; }.page-header { margin-bottom: 28px; }.page-description { max-width: 610px; margin-bottom: 0; }.loading, .card { padding: 24px; }.editor { display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: 16px; }.form-column { display: grid; gap: 14px; }.section-heading { display: flex; gap: 12px; align-items: flex-start; margin-bottom: 16px; }.section-heading > span { display: grid; width: 30px; height: 30px; place-items: center; border-radius: 50%; color: #93551e; background: #fff0d8; font-size: 12px; font-weight: 800; }.section-heading h2, .preview-card h2 { margin: 0; font-size: 18px; }.section-heading p, .field small { margin: 4px 0 0; color: var(--color-text-muted); font-size: 13px; }.field { display: grid; gap: 7px; color: var(--color-text-muted); font-size: 13px; font-weight: 750; }.two-fields { display: grid; grid-template-columns: 180px minmax(0, 1fr); gap: 14px; margin-top: 14px; }.field input, .field textarea { width: 100%; border: 1px solid var(--color-border); border-radius: var(--radius-input); padding: 9px 11px; color: var(--color-text); background: var(--color-surface-warm); font: inherit; }.upload-field { padding: 11px; border: 1px solid #efdbc1; border-radius: 12px; background: #fff8ed; }.upload-field input[type=file] { padding: 6px 0; background: transparent; }.field textarea { min-height: 96px; resize: vertical; }.star-picker { display: flex; gap: 6px; }.star-picker button { border: 0; padding: 0; background: transparent; color: #dfd2c4; font-size: 30px; line-height: 1; cursor: pointer; }.star-picker button.active { color: #ff9800; }.image-preview { display: flex; align-items: center; gap: 14px; margin-top: 14px; padding: 10px; border: 1px solid #efdbc1; border-radius: 12px; background: #fff8ed; }.image-preview img { width: 120px; height: 84px; object-fit: cover; border-radius: 8px; }.image-preview div { display: grid; gap: 8px; font-size: 13px; }.image-preview button { justify-self: start; min-height: 30px; border: 1px solid #edcfac; border-radius: 8px; padding: 0 9px; color: #93551e; background: #fff; }.group-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }.answer-group { padding: 12px; border: 1px solid var(--color-border); border-radius: 12px; background: #fffdf9; }.answer-group h3, .preview-group h3 { margin: 0 0 8px; color: #85451e; font-size: 14px; }.option, .preview-group span { display: inline-flex; align-items: center; gap: 7px; margin: 0 8px 8px 0; border: 1px solid transparent; border-radius: 999px; padding: 6px 9px; color: var(--color-text-muted); background: var(--color-surface-warm); font-size: 13px; cursor: pointer; }.option input { width: auto; margin: 0; }.option.selected, .preview-group .correct { border-color: #d58a45; color: #85451e; background: #fff0d8; }.preview { align-self: start; position: sticky; top: 20px; }.preview-label { margin: 0 0 8px; color: var(--color-text-muted); font-size: 13px; font-weight: 750; }.preview-card { background: #fffdf9; }.preview-card > img { width: 100%; max-height: 210px; object-fit: cover; border-radius: 10px; margin: 14px 0; }.preview-group { margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--color-border); }.save-bar { grid-column: 1 / -1; display: flex; align-items: center; justify-content: space-between; gap: 20px; padding: 16px 20px; border: 1px solid #efdbc1; border-radius: 14px; background: #fff8ed; }.save-bar p { margin: 0; color: var(--color-text-muted); font-size: 13px; }.save-bar button { min-height: 44px; border: 0; border-radius: var(--radius-button); padding: 0 20px; color: #fff; background: var(--color-action); font-weight: 750; }.save-bar button:disabled { opacity: .65; }
@media (max-width: 900px) { .admin-content { width: min(100% - 32px, 1120px); padding-top: 28px; }.editor { grid-template-columns: 1fr; }.preview { position: static; }.save-bar { grid-column: auto; } } @media (max-width: 600px) { .save-bar { flex-direction: column; }.two-fields, .group-grid { grid-template-columns: 1fr; }.save-bar button { width: 100%; } }
</style>
