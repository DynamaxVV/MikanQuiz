<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { ElMessage } from 'element-plus';
import { api } from '@/api/client';
import AdminShell from '@/components/AdminShell.vue';
import ErrorPanel from '@/components/ErrorPanel.vue';

const presets = ref<string[]>([]);
const rawText = ref('');
const entry = ref('');
const ready = ref(false);
const loading = ref(true);
const saving = ref(false);
const error = ref('');
const parsed = computed(() => rawText.value.split(/[\n,，]/).map((item) => item.trim()).filter(Boolean));

async function load(): Promise<void> {
  loading.value = true;
  error.value = '';
  try {
    const settings = await api.getAdminSettings();
    presets.value = settings.fontPresets;
    rawText.value = presets.value.join('\n');
    ready.value = true;
  } catch (caught) { error.value = caught instanceof Error ? caught.message : '字体快捷项加载失败。'; }
  finally { loading.value = false; }
}

function addPreset(): void {
  const value = entry.value.trim();
  if (value && !presets.value.includes(value)) presets.value = [...presets.value, value];
  entry.value = '';
  rawText.value = presets.value.join('\n');
}

function removePreset(preset: string): void { presets.value = presets.value.filter((item) => item !== preset); rawText.value = presets.value.join('\n'); }
function parseText(): void { presets.value = [...new Set(parsed.value)]; rawText.value = presets.value.join('\n'); }

async function save(): Promise<void> {
  saving.value = true;
  error.value = '';
  try { await api.saveFontPresets(presets.value); ElMessage.success('字体快捷项已保存'); }
  catch (caught) { error.value = caught instanceof Error ? caught.message : '字体快捷项保存失败。'; }
  finally { saving.value = false; }
}

onMounted(load);
</script>

<template><AdminShell><section class="admin-content" aria-labelledby="presets-title"><header><p class="eyebrow">题库设置</p><h1 id="presets-title" class="page-title">字体快捷项</h1><p class="page-description">编辑题目时，点击快捷项可替换当前聚焦的选项文本。</p></header><div v-if="loading" class="loading card">正在读取字体快捷项…</div><ErrorPanel v-else-if="error && !ready" :message="error" @retry="load" /><form v-else class="presets card" @submit.prevent="save"><section><h2>当前快捷项</h2><div v-if="presets.length" class="chips"><span v-for="preset in presets" :key="preset">{{ preset }}<button type="button" :aria-label="`移除 ${preset}`" @click="removePreset(preset)">×</button></span></div><p v-else class="empty-copy">还没有快捷项。可以在下方逐项添加，或粘贴多行文本。</p></section><label class="new-entry">添加一项<div><input v-model="entry" maxlength="100" placeholder="例如：宋体" @keyup.enter.prevent="addPreset" /><button type="button" @click="addPreset">添加</button></div></label><label class="bulk-entry">粘贴多行或逗号分隔内容<textarea v-model="rawText" rows="7" placeholder="每行一项字体名称" /></label><button type="button" class="parse" @click="parseText">解析并替换当前列表</button><p v-if="error" class="status-error" role="alert">{{ error }}</p><button type="submit" class="save" :disabled="saving">{{ saving ? '正在保存…' : '保存字体快捷项' }}</button></form></section></AdminShell></template>

<style scoped>
.admin-content { width: min(900px, calc(100% - 64px)); margin: 0 auto; padding: 48px 0 64px; }.page-description { max-width: 620px; }.loading, .presets { margin-top: 28px; padding: 28px; }.presets { display: grid; gap: 24px; }.presets h2 { margin: 0 0 12px; font-size: 18px; }.chips { display: flex; flex-wrap: wrap; gap: 8px; }.chips span { display: inline-flex; min-height: 34px; align-items: center; gap: 8px; border: 1px solid #edcfac; border-radius: 999px; padding: 0 8px 0 12px; color: #85451e; background: var(--color-surface-accent); }.chips button { width: 23px; height: 23px; border: 0; border-radius: 50%; color: #85451e; background: transparent; font-size: 18px; line-height: 1; }.chips button:hover { background: rgba(169, 79, 31, .14); }.empty-copy { color: var(--color-text-muted); }.new-entry, .bulk-entry { display: grid; gap: 8px; font-size: 14px; font-weight: 750; }.new-entry div { display: flex; gap: 8px; }.new-entry input, .bulk-entry textarea { width: 100%; border: 1px solid var(--color-border); border-radius: var(--radius-input); padding: 10px 12px; color: var(--color-text); background: var(--color-surface-warm); }.new-entry button, .parse { min-height: 42px; border: 1px solid var(--color-border); border-radius: 10px; padding: 0 14px; color: var(--color-text); background: #fff; font-weight: 700; white-space: nowrap; }.parse { justify-self: start; }.save { justify-self: start; min-height: 46px; border: 0; border-radius: var(--radius-button); padding: 0 20px; color: #fff; background: var(--color-action); font-weight: 750; }.save:disabled { opacity: .65; }
@media (max-width: 1023px) { .admin-content { width: min(100% - 32px, 900px); padding-top: 28px; } }
</style>
