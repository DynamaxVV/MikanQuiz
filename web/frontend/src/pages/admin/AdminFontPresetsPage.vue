<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { api } from '@/api/client';
import { useFontRendering } from '@/composables/useFontRendering';
import AdminShell from '@/components/AdminShell.vue';
import ErrorPanel from '@/components/ErrorPanel.vue';
import type { FontOption, OptionGroup } from '@/types';

const { fontStyle } = useFontRendering();
const protectedGroupNames = ['类黑', '类宋', '类圆', '类黑体', '类宋体', '类圆体'];
const groups = ref<OptionGroup[]>([]);
const loading = ref(true);
const saving = ref(false);
const error = ref('');
const dragged = ref<{ group: OptionGroup; index: number } | null>(null);
const uploadingFontFor = ref('');
const fontUploadProgress = ref(0);

function newOption(index: number): FontOption {
  return { id: '', name: '', fontUrl: undefined, minimumDifficulty: 1, sortOrder: index };
}

async function load(): Promise<void> {
  loading.value = true;
  error.value = '';
  try { groups.value = await api.getOptionGroups(); }
  catch (caught) { error.value = caught instanceof Error ? caught.message : '字体快捷项加载失败。'; }
  finally { loading.value = false; }
}

function addGroup(): void {
  groups.value.push({ id: '', name: '', sortOrder: groups.value.length, options: [] });
}

async function exportCatalog(): Promise<void> {
  try { await api.exportOptionGroups(); ElMessage.success('字体目录已导出'); }
  catch (caught) { ElMessage.error(caught instanceof Error ? caught.message : '导出失败'); }
}

function importCatalog(): void {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = '.json';
  input.onchange = async (e: Event) => {
    const file = (e.target as HTMLInputElement).files?.[0];
    if (!file) return;
    try {
      groups.value = await api.importOptionGroups(file);
      ElMessage.success('字体目录已导入');
    } catch (caught) { ElMessage.error(caught instanceof Error ? caught.message : '导入失败，请检查文件格式。'); }
  };
  input.click();
}

function addOption(group: OptionGroup): void { group.options.push(newOption(group.options.length)); }

function uploadFontFile(option: FontOption): void {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = '.ttf,.otf,.woff,.woff2';
  input.onchange = (e: Event) => {
    const file = (e.target as HTMLInputElement).files?.[0];
    if (!file) return;
    uploadingFontFor.value = option.id || option.name || '__new__';
    fontUploadProgress.value = 0;
    api.uploadFont(file, (pct) => { fontUploadProgress.value = pct; })
      .then((url) => { option.fontUrl = url; ElMessage.success('字体文件已上传'); void save(); })
      .catch((caught) => { ElMessage.error(caught instanceof Error ? caught.message : '字体上传失败'); })
      .finally(() => { uploadingFontFor.value = ''; fontUploadProgress.value = 0; });
  };
  input.click();
}

function clearFontFile(option: FontOption): void {
  option.fontUrl = undefined;
}

async function removeOption(group: OptionGroup, option: FontOption): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定删除字体"${option.name || '未命名字体'}"吗？已被题目使用的题目会变为待修复状态。`, '删除字体', {
      confirmButtonText: '删除字体', cancelButtonText: '取消', type: 'warning',
    });
    group.options.splice(group.options.indexOf(option), 1);
  } catch { /* 用户取消时不改变内容。 */ }
}

async function removeGroup(group: OptionGroup): Promise<void> {
  if (group.options.length) {
    ElMessage.warning('分区内仍有字体，不能删除。');
    return;
  }
  try {
    await ElMessageBox.confirm(`确定删除空分区"${group.name || '未命名分区'}"吗？`, '删除分区', {
      confirmButtonText: '删除分区', cancelButtonText: '取消', type: 'warning',
    });
    groups.value.splice(groups.value.indexOf(group), 1);
  } catch { /* 用户取消时不改变内容。 */ }
}

function dragStart(group: OptionGroup, index: number): void {
  dragged.value = { group, index };
}

function dropOption(targetGroup: OptionGroup, targetIndex: number): void {
  if (!dragged.value) return;
  const { group: sourceGroup, index: sourceIndex } = dragged.value;
  if (sourceGroup === targetGroup && sourceIndex === targetIndex) return;
  const [option] = sourceGroup.options.splice(sourceIndex, 1);
  targetGroup.options.splice(targetIndex, 0, option);
  dragged.value = null;
}

async function save(): Promise<void> {
  if (!groups.value.length || groups.value.some((group) => !group.name.trim() || group.options.some((option) => !option.name.trim()))) {
    error.value = '请填写每个分区和字体名称。';
    return;
  }
  saving.value = true;
  error.value = '';
  try {
    groups.value.forEach((group, groupIndex) => {
      group.sortOrder = groupIndex;
      group.options.forEach((option, optionIndex) => { option.sortOrder = optionIndex; });
    });
    groups.value = await api.saveOptionGroups(groups.value);
    ElMessage.success('字体快捷项已保存');
  } catch (caught) { error.value = caught instanceof Error ? caught.message : '字体快捷项保存失败。'; }
  finally { saving.value = false; }
}

onMounted(() => { void load(); });
</script>

<template>
  <AdminShell>
    <section class="admin-content" aria-labelledby="font-options-title">
      <header class="page-header">
        <div><p class="eyebrow">题库设置</p><h1 id="font-options-title" class="page-title">字体快捷项</h1><p class="page-description">拖动字体名可在分区间移动；上传字体后文字名以自身字体预览，加载期间显示系统字体。</p></div>
        <div class="header-actions">
          <button type="button" class="secondary" @click="exportCatalog">导出</button>
          <button type="button" class="secondary" @click="importCatalog">导入</button>
          <button type="button" class="secondary" @click="addGroup">添加分区</button>
        </div>
      </header>
      <div v-if="loading" class="loading card">正在读取字体快捷项…</div>
      <ErrorPanel v-else-if="error && !groups.length" :message="error" @retry="load" />
      <form v-else class="catalog" @submit.prevent="save">
        <article v-for="(group, groupIndex) in groups" :key="group.id || `new-${groupIndex}`" class="group-card card">
          <header class="group-header"><label>分区名称<input v-model="group.name" maxlength="100" placeholder="例如：类黑体" /></label><button v-if="!protectedGroupNames.includes(group.name)" type="button" class="text-danger" @click="removeGroup(group)">删除分区</button></header>
          <div class="option-list">
            <div
              v-for="(option, optionIndex) in group.options"
              :key="option.id || `new-${optionIndex}`"
              class="option-row"
              :class="{ 'is-uploading': uploadingFontFor && uploadingFontFor === (option.id || option.name || '__new__') }"
              @dragover.prevent
              @drop="dropOption(group, optionIndex)"
            >
              <span class="drag-mark" title="拖动可在分区间移动" draggable="true" @dragstart="dragStart(group, optionIndex)">⠿</span>
              <input
                v-model="option.name"
                maxlength="500"
                placeholder="字体名称，例如：黑体"
                :style="fontStyle(option)"
              />
              <label class="difficulty-label">最低难度<select v-model.number="option.minimumDifficulty"><option v-for="star in 3" :key="star" :value="star">{{ star }} 星</option></select></label>
              <div class="font-upload">
                <button
                  v-if="!option.fontUrl"
                  type="button"
                  class="font-upload-btn"
                  :disabled="uploadingFontFor === (option.id || option.name || '__new__')"
                  @click="uploadFontFile(option)"
                >
                  {{ uploadingFontFor === (option.id || option.name || '__new__') ? '上传中…' : '上传字体' }}
                </button>
                <div
                  v-if="uploadingFontFor === (option.id || option.name || '__new__')"
                  class="font-progress"
                >
                  <div class="font-progress-bar" :style="{ width: fontUploadProgress + '%' }"></div>
                </div>
                <span v-else-if="option.fontUrl" class="font-file">
                  <span class="font-file-name" :title="option.fontUrl">已上传</span>
                  <button type="button" class="font-clear-btn" title="移除字体文件（不删除该项）" @click="clearFontFile(option)">清除</button>
                </span>
              </div>
              <button type="button" class="remove-option" :aria-label="`删除 ${option.name || '该字体'}`" @click="removeOption(group, option)">×</button>
            </div>
          </div>
          <button type="button" class="add-option" @click="addOption(group)">＋ 添加字体</button>
        </article>
        <p v-if="error" class="status-error" role="alert">{{ error }}</p>
        <footer class="save-bar"><p>删除字体需确认；只有空分区才能删除。</p><button type="submit" :disabled="saving">{{ saving ? '正在保存…' : '保存字体快捷项' }}</button></footer>
      </form>
    </section>
  </AdminShell>
</template>

<style scoped>
.admin-content { width: min(860px, calc(100% - 64px)); margin: 0 auto; padding: 42px 0 56px; }
.page-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; margin-bottom: 20px; }
.header-actions { display: flex; gap: 8px; flex-shrink: 0; }
.secondary { min-height: 46px; border: 1px solid var(--color-border); border-radius: var(--radius-button); padding: 0 20px; color: var(--color-text); background: var(--color-surface); font-weight: 700; }
.page-description { margin-bottom: 0; }
.loading { padding: 22px; }
.catalog { display: grid; gap: 12px; }
.group-card { display: grid; grid-template-columns: 172px minmax(0, 1fr); padding: 0; overflow: hidden; }
.group-header { display: flex; flex-direction: column; justify-content: space-between; gap: 14px; padding: 12px; border-right: 1px solid #efdbc1; background: var(--color-surface-accent); }
.group-header label, .difficulty-label { display: grid; gap: 5px; color: var(--color-text-muted); font-size: 12px; font-weight: 750; }
.group-header input { width: 100%; border: 0; border-bottom: 1px solid #d8b789; padding: 5px 0; color: var(--color-text); background: transparent; font-size: 15px; font-weight: 750; }
.option-list { display: grid; padding: 2px 12px; }
.option-row { display: grid; grid-template-columns: 20px minmax(0, 1fr) 104px 108px 26px; align-items: end; gap: 4px; padding: 4px 0; border-bottom: 1px solid var(--color-border); transition: opacity .2s; }
.option-row.is-uploading { opacity: .65; }
.drag-mark { display: grid; width: 20px; height: 26px; place-items: center; color: #9a652d; font-size: 17px; line-height: 1; cursor: grab; }
.drag-mark:active { cursor: grabbing; }
.option-row > input, select { height: 32px; line-height: 1; border: 1px solid var(--color-border); border-radius: 8px; padding: 0 7px; color: var(--color-text); background: var(--color-surface-warm); font-size: 12px; }
/* font upload area */
.font-upload { display: flex; flex-direction: column; gap: 3px; font-size: 12px; }
.font-upload-btn { width: 100%; height: 32px; border: 1px dashed #d7aa73; border-radius: 8px; padding: 0 6px; color: #9a652d; background: transparent; font-size: 11px; cursor: pointer; white-space: nowrap; transition: background .15s; }
.font-upload-btn:hover { background: #fdf3e4; }
.font-upload-btn:disabled { opacity: .5; cursor: not-allowed; }
.font-progress { width: 100%; height: 3px; border-radius: 2px; background: #ede1cf; overflow: hidden; }
.font-progress-bar { height: 100%; border-radius: 2px; background: var(--color-action); transition: width .2s ease; }
.font-file { display: flex; align-items: center; justify-content: space-between; gap: 4px; width: 100%; height: 32px; border: 1px solid #78b63c; border-radius: 8px; padding: 0 6px; background: #ecf8df; }
.font-file-name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #3e6b14; font-size: 11px; font-weight: 650; }
.font-clear-btn { flex-shrink: 0; min-height: 20px; border: 1px solid #b8d99a; border-radius: 6px; padding: 0 6px; color: #5a8a2f; background: #fff; font-size: 11px; font-weight: 650; cursor: pointer; transition: background .15s; }
.font-clear-btn:hover { background: #fefefc; }
.remove-option, .text-danger { border: 0; background: transparent; color: var(--color-danger); font-weight: 700; }
.text-danger { align-self: flex-start; padding: 5px 0; }
.remove-option { width: 22px; height: 22px; border-radius: 50%; font-size: 16px; }
.remove-option:hover, .text-danger:hover { background: #fff0ee; }
.add-option { justify-self: start; margin: 8px 12px 10px; border: 1px dashed #d7aa73; border-radius: 8px; padding: 4px 8px; color: var(--color-action); background: transparent; font-size: 13px; cursor: pointer; }
.save-bar { display: flex; align-items: center; justify-content: space-between; padding: 16px 20px; border: 1px solid #efdbc1; border-radius: 14px; background: #fff8ed; }
.save-bar p { margin: 0; color: var(--color-text-muted); font-size: 13px; }
.save-bar button { min-height: 44px; border: 0; border-radius: var(--radius-button); padding: 0 20px; color: #fff; background: var(--color-action); font-weight: 750; }
@media (max-width: 760px) {
  .admin-content { width: min(100% - 32px, 860px); padding-top: 28px; }
  .page-header, .save-bar { align-items: flex-start; flex-direction: column; }
  .group-card { grid-template-columns: 1fr; }
  .group-header { gap: 10px; border-right: 0; border-bottom: 1px solid #efdbc1; }
  .option-row { grid-template-columns: 20px minmax(0, 1fr) 26px; }
  .difficulty-label, .font-upload { grid-column: 2; }
  .save-bar button { width: 100%; }
}
</style>
