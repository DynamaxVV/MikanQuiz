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
const difficulty = ref(1);
const loading = ref(true);
const uploading = ref(false);
const saving = ref(false);
const error = ref('');
const editId = ref('');

async function load(): Promise<void> {
  loading.value = true;
  error.value = '';
  try { references.value = await api.listFontReferences(); }
  catch (caught) { error.value = caught instanceof Error ? caught.message : '嵌字笔记加载失败。'; }
  finally { loading.value = false; }
}

function resetForm(): void {
  title.value = '';
  note.value = '';
  imageUrl.value = '';
  difficulty.value = 1;
  editId.value = '';
  error.value = '';
}

function startEdit(item: FontReference): void {
  editId.value = item.id;
  title.value = item.title;
  note.value = item.note;
  imageUrl.value = item.imageUrl;
  difficulty.value = item.difficulty;
  error.value = '';
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
  } finally { uploading.value = false; }
}

async function save(): Promise<void> {
  if (!title.value.trim() || !imageUrl.value) {
    error.value = '请填写标题并上传图片。';
    return;
  }
  saving.value = true;
  error.value = '';
  try {
    if (editId.value) {
      const updated = await api.updateFontReference(editId.value, {
        title: title.value,
        note: note.value,
        imageUrl: imageUrl.value,
        difficulty: difficulty.value,
      });
      const idx = references.value.findIndex((r) => r.id === editId.value);
      if (idx >= 0) references.value[idx] = updated;
      ElMessage.success('卡片已更新');
    } else {
      const item = await api.createFontReference({
        title: title.value,
        note: note.value,
        imageUrl: imageUrl.value,
        difficulty: difficulty.value,
      });
      references.value = [item, ...references.value];
      ElMessage.success('卡片已发布');
    }
    resetForm();
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '保存失败。';
  } finally { saving.value = false; }
}

async function remove(item: FontReference): Promise<void> {
  await ElMessageBox.confirm(`确定删除「${item.title}」吗？删除后公开页将不再显示。`, '删除卡片', { type: 'warning' });
  try {
    await api.deleteFontReference(item.id);
    references.value = references.value.filter((entry) => entry.id !== item.id);
    if (editId.value === item.id) resetForm();
    ElMessage.success('卡片已删除');
  } catch (caught) {
    if (caught !== 'cancel') error.value = caught instanceof Error ? caught.message : '删除失败。';
  }
}

function stars(count: number): string { return '★'.repeat(count) + '☆'.repeat(3 - count); }

onMounted(load);
</script>

<template>
  <AdminShell>
    <section class="admin-content" aria-labelledby="font-reference-admin-title">
      <header>
        <p class="eyebrow">公开内容</p>
        <h1 id="font-reference-admin-title" class="page-title">嵌字笔记管理</h1>
        <p class="page-description">管理嵌字笔记卡片，支持标题、图片、说明与难度星级设置。</p>
      </header>

      <div v-if="loading" class="loading card">正在读取卡片…</div>
      <ErrorPanel v-else-if="error && references.length === 0" :message="error" @retry="load" />

      <template v-else>
        <form class="create-form card" @submit.prevent="save">
          <h2>{{ editId ? '编辑卡片' : '新增卡片' }}</h2>

          <label>标题<input v-model="title" maxlength="100" required placeholder="例如：宋体与仿宋对照" /></label>

          <label>难度星级
            <div class="difficulty-picker">
              <button v-for="star in 3" :key="star" type="button" :class="{ active: difficulty >= star }" @click="difficulty = star">{{ '★' }}</button>
            </div>
          </label>

          <label>图片
            <input accept="image/jpeg,image/png,image/gif,image/webp" type="file" :disabled="uploading" @change="upload" />
            <small>{{ uploading ? '正在上传图片…' : imageUrl ? '图片已上传。' : '支持 JPG、PNG、GIF、WebP，最大 8MB。' }}</small>
          </label>
          <img v-if="imageUrl" class="preview" :src="imageUrl" alt="待发布的卡片预览" />

          <label>说明（可选）<textarea v-model="note" maxlength="500" rows="3" placeholder="描述这张卡片对应的字形特征或适用场景" /></label>

          <p v-if="error" class="status-error" role="alert">{{ error }}</p>

          <div class="form-actions">
            <button class="publish" type="submit" :disabled="saving || uploading">{{ saving ? '正在保存…' : editId ? '更新卡片' : '发布卡片' }}</button>
            <button v-if="editId" type="button" class="cancel" @click="resetForm">取消编辑</button>
          </div>
        </form>

        <section class="reference-list card" aria-label="已发布卡片">
          <h2>已发布（{{ references.length }}）</h2>
          <p v-if="references.length === 0" class="empty-copy">还没有已发布的卡片。</p>
          <article v-for="item in references" :key="item.id">
            <img :src="item.imageUrl" :alt="item.title" />
            <div class="item-info">
              <h3>{{ item.title }} <span class="item-stars">{{ stars(item.difficulty) }}</span></h3>
              <p v-if="item.note">{{ item.note }}</p>
              <small>{{ new Date(item.createdAt).toLocaleString('zh-CN') }}</small>
            </div>
            <div class="item-actions">
              <button type="button" class="edit" @click="startEdit(item)">编辑</button>
              <button type="button" class="delete" @click="remove(item)">删除</button>
            </div>
          </article>
        </section>
      </template>
    </section>
  </AdminShell>
</template>

<style scoped>
.admin-content { width: min(1000px, calc(100% - 64px)); margin: 0 auto; padding: 48px 0 64px; }
.page-description { max-width: 640px; }
.loading, .create-form, .reference-list { margin-top: 28px; padding: 28px; }
.create-form { display: grid; gap: 18px; }
.create-form h2, .reference-list h2 { margin: 0; font-size: 18px; }
.create-form label { display: grid; gap: 8px; color: var(--color-text); font-size: 14px; font-weight: 750; }
.create-form input, .create-form textarea { width: 100%; border: 1px solid var(--color-border); border-radius: var(--radius-input); padding: 10px 12px; color: var(--color-text); background: var(--color-surface-warm); box-sizing: border-box; }
.create-form small, .reference-list small { color: var(--color-text-muted); font-weight: 500; }
.difficulty-picker { display: flex; gap: 6px; }
.difficulty-picker button { border: 0; padding: 0; background: transparent; color: #dfd2c4; font-size: 30px; line-height: 1; cursor: pointer; }
.difficulty-picker button.active { color: #ff9800; }
.preview { width: min(100%, 640px); max-height: 300px; object-fit: contain; border: 1px solid var(--color-border); border-radius: 12px; background: var(--color-surface-warm); }
.form-actions { display: flex; gap: 12px; align-items: center; }
.publish { min-height: 44px; border: 0; border-radius: var(--radius-button); padding: 0 18px; color: #fff; background: var(--color-action); font-weight: 750; cursor: pointer; }
.publish:disabled { opacity: .65; }
.cancel { min-height: 44px; border: 1px solid var(--color-border); border-radius: var(--radius-button); padding: 0 18px; color: var(--color-text-muted); background: var(--color-surface); font-weight: 750; cursor: pointer; }
.reference-list { display: grid; gap: 14px; }
.reference-list article { display: grid; grid-template-columns: 144px minmax(0, 1fr) auto; gap: 18px; align-items: center; border-top: 1px solid var(--color-border); padding-top: 14px; }
.reference-list article img { width: 144px; height: 96px; object-fit: cover; border-radius: 10px; background: var(--color-surface-warm); }
.item-info h3 { margin: 0; display: flex; align-items: center; gap: 10px; }
.item-info p { margin: 7px 0 0; color: var(--color-text-muted); line-height: 1.55; white-space: pre-wrap; }
.item-stars { color: #e8a317; font-size: 14px; letter-spacing: 1px; }
.item-actions { display: flex; gap: 8px; }
.edit { min-height: 36px; border: 1px solid var(--color-border); border-radius: var(--radius-button); padding: 0 14px; color: var(--color-text); background: var(--color-surface); font-weight: 600; font-size: 13px; cursor: pointer; }
.delete { min-height: 36px; border: 0; border-radius: var(--radius-button); padding: 0 14px; color: #a1372d; background: #fff0ee; font-weight: 600; font-size: 13px; cursor: pointer; }
.empty-copy { color: var(--color-text-muted); }
.status-error { margin: 0; color: #a1372d; }

@media (max-width: 1023px) { .admin-content { width: min(100% - 32px, 1000px); padding-top: 28px; } .reference-list article { grid-template-columns: 112px minmax(0, 1fr) auto; } .reference-list article img { width: 112px; height: 80px; } }
@media (max-width: 620px) { .reference-list article { grid-template-columns: 1fr; gap: 12px; } .reference-list article img { width: 100%; height: 180px; } .item-actions { justify-self: start; } }
</style>
