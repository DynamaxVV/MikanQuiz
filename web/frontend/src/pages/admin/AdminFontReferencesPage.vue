<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { api } from '@/api/client';
import AdminShell from '@/components/AdminShell.vue';
import ErrorPanel from '@/components/ErrorPanel.vue';
import type { FontReference } from '@/types';

const references = ref<FontReference[]>([]);
const title = ref('');
const note = ref('');
const imageUrl = ref('');
const loading = ref(true);
const uploading = ref(false);
const saving = ref(false);
const error = ref('');

async function load(): Promise<void> {
  loading.value = true;
  error.value = '';
  try { references.value = await api.listFontReferences(); }
  catch (caught) { error.value = caught instanceof Error ? caught.message : '字体对照图加载失败。'; }
  finally { loading.value = false; }
}

async function upload(event: Event): Promise<void> {
  const file = (event.target as HTMLInputElement).files?.[0];
  if (!file) return;
  uploading.value = true;
  error.value = '';
  try {
    imageUrl.value = await api.uploadImage(file);
    ElMessage.success('图片已上传');
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '图片上传失败。';
  } finally {
    uploading.value = false;
  }
}

async function create(): Promise<void> {
  if (!title.value.trim() || !imageUrl.value) {
    error.value = '请填写标题并上传图片。';
    return;
  }
  saving.value = true;
  error.value = '';
  try {
    const item = await api.createFontReference({ title: title.value, note: note.value, imageUrl: imageUrl.value });
    references.value = [item, ...references.value];
    title.value = '';
    note.value = '';
    imageUrl.value = '';
    ElMessage.success('字体对照图已发布');
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '字体对照图发布失败。';
  } finally {
    saving.value = false;
  }
}

async function remove(item: FontReference): Promise<void> {
  await ElMessageBox.confirm(`确定删除“${item.title}”吗？删除后公开页将不再显示。`, '删除字体对照图', { type: 'warning' });
  try {
    await api.deleteFontReference(item.id);
    references.value = references.value.filter((entry) => entry.id !== item.id);
    ElMessage.success('字体对照图已删除');
  } catch (caught) {
    if (caught !== 'cancel') error.value = caught instanceof Error ? caught.message : '删除失败。';
  }
}

onMounted(load);
</script>

<template>
  <AdminShell>
    <section class="admin-content" aria-labelledby="font-reference-admin-title">
      <header><p class="eyebrow">公开内容</p><h1 id="font-reference-admin-title" class="page-title">字体对照表管理</h1><p class="page-description">上传对照图片，补充标题和注释后即可在公开页展示。</p></header>
      <div v-if="loading" class="loading card">正在读取字体对照图…</div>
      <ErrorPanel v-else-if="error && references.length === 0" :message="error" @retry="load" />
      <template v-else>
        <form class="create-form card" @submit.prevent="create">
          <h2>新增对照图</h2>
          <label>标题<input v-model="title" maxlength="100" required placeholder="例如：宋体与仿宋对照" /></label>
          <label>图片<input accept="image/jpeg,image/png,image/gif,image/webp" type="file" :disabled="uploading" @change="upload" /><small>{{ uploading ? '正在上传图片…' : imageUrl ? '图片已上传，发布后公开展示。' : '支持 JPG、PNG、GIF、WebP，最大 8MB。' }}</small></label>
          <img v-if="imageUrl" class="preview" :src="imageUrl" alt="待发布的字体对照图预览" />
          <label>注释（可选）<textarea v-model="note" maxlength="500" rows="3" placeholder="说明这张对照图的适用场景或观察要点" /></label>
          <p v-if="error" class="status-error" role="alert">{{ error }}</p>
          <button class="publish" type="submit" :disabled="saving || uploading">{{ saving ? '正在发布…' : '发布字体对照图' }}</button>
        </form>
        <section class="reference-list card" aria-label="已发布字体对照图"><h2>已发布（{{ references.length }}）</h2><p v-if="references.length === 0" class="empty-copy">还没有已发布的字体对照图。</p><article v-for="item in references" :key="item.id"><img :src="item.imageUrl" :alt="item.title" /><div><h3>{{ item.title }}</h3><p v-if="item.note">{{ item.note }}</p><small>{{ new Date(item.createdAt).toLocaleString('zh-CN') }}</small></div><button type="button" class="delete" @click="remove(item)">删除</button></article></section>
      </template>
    </section>
  </AdminShell>
</template>

<style scoped>
.admin-content { width: min(1000px, calc(100% - 64px)); margin: 0 auto; padding: 48px 0 64px; }.page-description { max-width: 640px; }.loading, .create-form, .reference-list { margin-top: 28px; padding: 28px; }.create-form { display: grid; gap: 18px; }.create-form h2, .reference-list h2 { margin: 0; font-size: 18px; }.create-form label { display: grid; gap: 8px; color: var(--color-text); font-size: 14px; font-weight: 750; }.create-form input, .create-form textarea { width: 100%; border: 1px solid var(--color-border); border-radius: var(--radius-input); padding: 10px 12px; color: var(--color-text); background: var(--color-surface-warm); }.create-form small, .reference-list small { color: var(--color-text-muted); font-weight: 500; }.preview { width: min(100%, 640px); max-height: 300px; object-fit: contain; border: 1px solid var(--color-border); border-radius: 12px; background: var(--color-surface-warm); }.publish, .delete { min-height: 44px; border: 0; border-radius: var(--radius-button); padding: 0 18px; color: #fff; background: var(--color-action); font-weight: 750; justify-self: start; }.publish:disabled { opacity: .65; }.reference-list { display: grid; gap: 14px; }.reference-list article { display: grid; grid-template-columns: 144px minmax(0, 1fr) auto; gap: 18px; align-items: center; border-top: 1px solid var(--color-border); padding-top: 14px; }.reference-list article img { width: 144px; height: 96px; object-fit: cover; border-radius: 10px; background: var(--color-surface-warm); }.reference-list h3, .reference-list p { margin: 0; }.reference-list p { margin-top: 7px; color: var(--color-text-muted); line-height: 1.55; white-space: pre-wrap; }.delete { color: #a1372d; background: #fff0ee; }.empty-copy { color: var(--color-text-muted); }.status-error { margin: 0; color: #a1372d; }
@media (max-width: 1023px) { .admin-content { width: min(100% - 32px, 1000px); padding-top: 28px; }.reference-list article { grid-template-columns: 112px minmax(0, 1fr) auto; }.reference-list article img { width: 112px; height: 80px; } }
@media (max-width: 620px) { .reference-list article { grid-template-columns: 1fr; }.reference-list article img { width: 100%; height: 180px; }.delete { justify-self: start; } }
</style>
