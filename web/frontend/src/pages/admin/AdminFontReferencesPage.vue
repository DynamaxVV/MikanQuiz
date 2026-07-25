<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { api } from '@/api/client';
import AdminShell from '@/components/AdminShell.vue';
import ErrorPanel from '@/components/ErrorPanel.vue';
import type { FontReference, FontReferenceSection } from '@/types';

const sections = ref<FontReferenceSection[]>([]);
const loading = ref(true);
const saving = ref(false);
const error = ref('');
const draggedCard = ref<{ sectionIndex: number; cardIndex: number } | null>(null);
const draggedSection = ref<number | null>(null);
const uploading = ref(false);

const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];

function newCard(): FontReference {
  return { id: '', title: '', imageUrl: '', note: '', difficulty: 1, sortOrder: 0, createdAt: '' };
}

async function load(): Promise<void> {
  loading.value = true;
  error.value = '';
  try { sections.value = await api.getFontReferenceSections(); }
  catch (caught) { error.value = caught instanceof Error ? caught.message : '嵌字笔记加载失败。'; }
  finally { loading.value = false; }
}

function addSection(): void {
  sections.value.push({ id: '', name: '', sortOrder: sections.value.length, cards: [] });
}

function addCard(section: FontReferenceSection): void {
  section.cards.push(newCard());
}

async function removeSection(section: FontReferenceSection): Promise<void> {
  if (section.cards.length) {
    ElMessage.warning('分区内仍有卡片，不能删除。');
    return;
  }
  try {
    await ElMessageBox.confirm(`确定删除空分区"${section.name || '未命名分区'}"吗？`, '删除分区', {
      confirmButtonText: '删除分区', cancelButtonText: '取消', type: 'warning',
    });
    sections.value.splice(sections.value.indexOf(section), 1);
  } catch { /* 用户取消 */ }
}

async function removeCard(section: FontReferenceSection, card: FontReference): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定删除卡片"${card.title || '未命名卡片'}"吗？`, '删除卡片', {
      confirmButtonText: '删除卡片', cancelButtonText: '取消', type: 'warning',
    });
    section.cards.splice(section.cards.indexOf(card), 1);
  } catch { /* 用户取消 */ }
}

function setCardDragImage(event: DragEvent, sectionIndex: number, cardIndex: number): void {
  const card = sections.value[sectionIndex]?.cards[cardIndex];
  if (!card || !event.dataTransfer) return;
  const ghost = document.createElement('div');
  ghost.textContent = card.title || '卡片';
  ghost.style.cssText = 'position:fixed;left:-9999px;top:0;padding:8px 14px;border-radius:8px;background:#fff8ed;border:1px solid #d7aa73;font-size:13px;font-weight:600;color:#5a3e28;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;';
  document.body.appendChild(ghost);
  event.dataTransfer.setDragImage(ghost, 0, 0);
  requestAnimationFrame(() => ghost.remove());
}

function setSectionDragImage(event: DragEvent, sectionIndex: number): void {
  const section = sections.value[sectionIndex];
  if (!section || !event.dataTransfer) return;
  const ghost = document.createElement('div');
  ghost.textContent = section.name || '分区';
  ghost.style.cssText = 'position:fixed;left:-9999px;top:0;padding:10px 16px;border-radius:10px;background:#fff;border:1px solid #efdbc1;font-size:14px;font-weight:700;color:#5a3e28;box-shadow:0 4px 12px rgba(0,0,0,.08);max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;';
  document.body.appendChild(ghost);
  event.dataTransfer.setDragImage(ghost, 0, 0);
  requestAnimationFrame(() => ghost.remove());
}

function cardDragStart(event: DragEvent, sectionIndex: number, cardIndex: number): void {
  event.stopPropagation();
  draggedCard.value = { sectionIndex, cardIndex };
  event.dataTransfer?.setData('application/x-card', '');
  setCardDragImage(event, sectionIndex, cardIndex);
}

function cardDragOver(event: DragEvent): void {
  if (event.dataTransfer?.types.includes('application/x-card')) {
    event.preventDefault();
    event.stopPropagation();
  }
}

function cardDrop(event: DragEvent, targetSectionIndex: number, targetCardIndex: number): void {
  event.stopPropagation();
  if (!draggedCard.value) return;
  const { sectionIndex: srcSecIdx, cardIndex: srcCardIdx } = draggedCard.value;
  if (srcSecIdx === targetSectionIndex && srcCardIdx === targetCardIndex) return;
  const srcSection = sections.value[srcSecIdx];
  const targetSection = sections.value[targetSectionIndex];
  const [card] = srcSection.cards.splice(srcCardIdx, 1);
  targetSection.cards.splice(targetCardIndex, 0, card);
  draggedCard.value = null;
}

function sectionDragStart(event: DragEvent, sectionIndex: number): void {
  event.stopPropagation();
  draggedSection.value = sectionIndex;
  event.dataTransfer?.setData('application/x-section', '');
  setSectionDragImage(event, sectionIndex);
}

function sectionDrop(event: DragEvent, targetIndex: number): void {
  if (draggedCard.value) {
    const { sectionIndex: srcSecIdx, cardIndex: srcCardIdx } = draggedCard.value;
    const srcSection = sections.value[srcSecIdx];
    const targetSection = sections.value[targetIndex];
    const [card] = srcSection.cards.splice(srcCardIdx, 1);
    targetSection.cards.push(card);
    draggedCard.value = null;
    return;
  }
  if (draggedSection.value === null || draggedSection.value === targetIndex) return;
  const [section] = sections.value.splice(draggedSection.value, 1);
  sections.value.splice(targetIndex, 0, section);
  draggedSection.value = null;
}

function onDragEnd(): void {
  draggedCard.value = null;
  draggedSection.value = null;
}

async function onImageInput(event: Event, card: FontReference): Promise<void> {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  if (!ACCEPTED_TYPES.includes(file.type)) {
    ElMessage.error('仅支持 JPEG、PNG、GIF、WebP 格式的图片');
    return;
  }
  uploading.value = true;
  try {
    card.imageUrl = await api.uploadImage(file);
    ElMessage.success('图片已上传');
  } catch (caught) {
    ElMessage.error(caught instanceof Error ? caught.message : '图片上传失败');
  } finally { uploading.value = false; }
}

function onPaste(event: ClipboardEvent, card: FontReference): void {
  const items = event.clipboardData?.items;
  if (!items) return;
  for (const item of items) {
    if (item.type.startsWith('image/')) {
      const blob = item.getAsFile();
      if (!blob) continue;
      if (!ACCEPTED_TYPES.includes(blob.type)) {
        ElMessage.error('仅支持 JPEG、PNG、GIF、WebP 格式的图片');
        continue;
      }
      event.preventDefault();
      const ext = blob.type.split('/')[1] || 'png';
      const file = new File([blob], `clipboard.${ext}`, { type: blob.type });
      uploading.value = true;
      api.uploadImage(file)
        .then((url) => { card.imageUrl = url; ElMessage.success('图片已粘贴并上传'); })
        .catch((caught) => { ElMessage.error(caught instanceof Error ? caught.message : '图片上传失败'); })
        .finally(() => { uploading.value = false; });
      return;
    }
  }
}

async function save(): Promise<void> {
  saving.value = true;
  error.value = '';
  try {
    sections.value.forEach((section, sectionIndex) => {
      section.sortOrder = sectionIndex;
      section.cards.forEach((card, cardIndex) => { card.sortOrder = cardIndex; });
    });
    sections.value = await api.saveFontReferenceSections(sections.value);
    ElMessage.success('嵌字笔记已保存');
  } catch (caught) { error.value = caught instanceof Error ? caught.message : '嵌字笔记保存失败。'; }
  finally { saving.value = false; }
}

onMounted(() => { void load(); });
</script>

<template>
  <AdminShell>
    <section class="admin-content" aria-labelledby="font-reference-admin-title">
      <header class="page-header">
        <div>
          <p class="eyebrow">公开内容</p>
          <h1 id="font-reference-admin-title" class="page-title">嵌字笔记管理</h1>
          <p class="page-description">拖动卡片可在分区间移动或调整顺序；拖拽分区标题可调整分区显示顺序。</p>
        </div>
        <button type="button" class="secondary" @click="addSection">添加分区</button>
      </header>
      <div v-if="loading" class="loading card">正在读取卡片…</div>
      <ErrorPanel v-else-if="error && !sections.length" :message="error" @retry="load" />
      <form v-else class="catalog" @submit.prevent="save">
        <article
          v-for="(section, sectionIndex) in sections"
          :key="section.id || `new-${sectionIndex}`"
          class="section-card card"
          :class="{ dragging: draggedSection === sectionIndex }"
          @dragover.prevent
          @drop="sectionDrop($event, sectionIndex)"
        >
          <header class="section-header">
            <span class="drag-mark" title="拖动可调整分区顺序" draggable="true" @dragstart="sectionDragStart($event, sectionIndex)" @dragend="onDragEnd">⠿</span>
            <label>分区名称<input v-model="section.name" maxlength="100" placeholder="例如：笔画粗细对比" /></label>
            <button type="button" class="text-danger" @click="removeSection(section)">删除分区</button>
          </header>
          <div class="card-list">
            <div
              v-for="(card, cardIndex) in section.cards"
              :key="card.id || `new-${cardIndex}`"
              class="card-row"
              @dragover="cardDragOver"
              @drop="cardDrop($event, sectionIndex, cardIndex)"
            >
              <span class="drag-mark" title="拖动可在分区间移动或排序" draggable="true" @dragstart="cardDragStart($event, sectionIndex, cardIndex)" @dragend="onDragEnd">⠿</span>
              <div class="card-preview" @click="(e: Event) => { const inp = (e.currentTarget as HTMLElement).querySelector('input') as HTMLInputElement; inp?.click(); }" @paste.prevent="(e: ClipboardEvent) => onPaste(e, card)">
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/gif,image/webp"
                  hidden
                  :disabled="uploading"
                  @change="(e: Event) => onImageInput(e, card)"
                />
                <template v-if="card.imageUrl">
                  <img :src="card.imageUrl" alt="卡片预览" />
                </template>
                <template v-else>
                  <span class="no-image">点击选图 或 Ctrl+V 粘贴</span>
                </template>
              </div>
              <div class="card-fields">
                <label>标题<input v-model="card.title" maxlength="100" placeholder="例如：细宋体笔画收尾" /></label>
                <label>说明<textarea v-model="card.note" maxlength="500" rows="2" placeholder="笔记内容（可选）" /></label>
                <label class="difficulty-label">难度
                  <div class="difficulty-picker">
                    <button v-for="star in 3" :key="star" type="button" :class="{ active: card.difficulty >= star }" @click="card.difficulty = star">{{ '★' }}</button>
                  </div>
                </label>
              </div>
              <button type="button" class="remove-card" :aria-label="`删除 ${card.title || '卡片'}`" @click="removeCard(section, card)">×</button>
            </div>
          </div>
          <button type="button" class="add-card" @click="addCard(section)">＋ 添加卡片</button>
        </article>

        <p v-if="error" class="status-error" role="alert">{{ error }}</p>
        <footer class="save-bar">
          <p>删除卡片需确认；只有空分区才能删除。</p>
          <button type="submit" :disabled="saving || uploading">{{ saving ? '正在保存…' : '保存嵌字笔记' }}</button>
        </footer>
      </form>
    </section>
  </AdminShell>
</template>

<style scoped>
.admin-content { width: min(900px, calc(100% - 64px)); margin: 0 auto; padding: 42px 0 56px; }
.page-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; margin-bottom: 20px; }
.secondary { min-height: 46px; border: 1px solid var(--color-border); border-radius: var(--radius-button); padding: 0 20px; color: var(--color-text); background: var(--color-surface); font-weight: 700; flex-shrink: 0; cursor: pointer; }
.page-description { margin-bottom: 0; }
.loading { padding: 22px; }
.catalog { display: grid; gap: 12px; }
.section-card { padding: 0; overflow: hidden; }
.section-card.dragging { opacity: .5; }
.section-header { display: flex; align-items: center; gap: 12px; padding: 10px 12px; background: var(--color-surface-accent); border-bottom: 1px solid #efdbc1; }
.section-header .drag-mark { display: grid; width: 20px; height: 26px; place-items: center; color: #9a652d; font-size: 17px; cursor: grab; }
.section-header .drag-mark:active { cursor: grabbing; }
.section-header label { display: grid; gap: 5px; color: var(--color-text-muted); font-size: 12px; font-weight: 750; flex: 1; }
.section-header input { width: 100%; border: 0; border-bottom: 1px solid #d8b789; padding: 5px 0; color: var(--color-text); background: transparent; font-size: 15px; font-weight: 750; box-sizing: border-box; }

.card-list { display: grid; }
.card-row { display: grid; grid-template-columns: 20px 100px minmax(0, 1fr) 26px; gap: 8px; align-items: start; padding: 10px 12px; border-bottom: 1px solid var(--color-border); }
.card-row .drag-mark { display: grid; width: 20px; height: 26px; place-items: center; color: #9a652d; font-size: 17px; padding-top: 4px; cursor: grab; }
.card-row .drag-mark:active { cursor: grabbing; }
.card-preview { width: 100px; height: 72px; border: 2px dashed #dcc6ae; border-radius: 8px; display: flex; align-items: center; justify-content: center; overflow: hidden; cursor: pointer; background: #fff8ed; }
.card-preview img { width: 100%; height: 100%; object-fit: cover; }
.no-image { font-size: 10px; color: var(--color-text-muted); text-align: center; padding: 4px; }
.card-fields { display: grid; gap: 6px; }
.card-fields label { display: grid; gap: 3px; color: var(--color-text-muted); font-size: 11px; font-weight: 700; }
.card-fields input, .card-fields textarea { width: 100%; border: 1px solid var(--color-border); border-radius: 6px; padding: 5px 8px; color: var(--color-text); background: var(--color-surface-warm); font-size: 12px; box-sizing: border-box; }
.card-fields textarea { resize: vertical; min-height: 44px; }
.difficulty-picker { display: flex; gap: 4px; }
.difficulty-picker button { border: 0; padding: 0; background: transparent; color: #dfd2c4; font-size: 22px; line-height: 1; cursor: pointer; }
.difficulty-picker button.active { color: #ff9800; }
.remove-card, .text-danger { border: 0; background: transparent; color: var(--color-danger); font-weight: 700; cursor: pointer; }
.text-danger { align-self: center; padding: 5px 0; font-size: 13px; white-space: nowrap; }
.remove-card { width: 22px; height: 22px; border-radius: 50%; font-size: 16px; padding: 0; }
.remove-card:hover, .text-danger:hover { background: #fff0ee; }
.add-card { justify-self: start; margin: 8px 12px 10px; border: 1px dashed #d7aa73; border-radius: 8px; padding: 4px 8px; color: var(--color-action); background: transparent; font-size: 13px; cursor: pointer; }
.status-error { margin: 0; color: #a1372d; }
.save-bar { display: flex; align-items: center; justify-content: space-between; padding: 16px 20px; border: 1px solid #efdbc1; border-radius: 14px; background: #fff8ed; }
.save-bar p { margin: 0; color: var(--color-text-muted); font-size: 13px; }
.save-bar button { min-height: 44px; border: 0; border-radius: var(--radius-button); padding: 0 20px; color: #fff; background: var(--color-action); font-weight: 750; cursor: pointer; }
.save-bar button:disabled { opacity: .65; }

@media (max-width: 760px) {
  .admin-content { width: min(100% - 32px, 900px); padding-top: 28px; }
  .page-header, .save-bar { align-items: flex-start; flex-direction: column; }
  .card-row { grid-template-columns: 20px minmax(0, 1fr) 26px; }
  .card-preview { grid-column: 2; width: 100%; height: 120px; }
  .save-bar button { width: 100%; }
}
</style>
