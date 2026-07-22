<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { api } from '@/api/client';
import AdminShell from '@/components/AdminShell.vue';
import ErrorPanel from '@/components/ErrorPanel.vue';
import type { FontOption, OptionGroup } from '@/types';

const groups = ref<OptionGroup[]>([]);
const loading = ref(true);
const saving = ref(false);
const error = ref('');
const dragged = ref<{ group: OptionGroup; index: number } | null>(null);

function newOption(index: number): FontOption {
  return { id: '', name: '', minimumDifficulty: 1, sortOrder: index };
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

function addOption(group: OptionGroup): void { group.options.push(newOption(group.options.length)); }

async function removeOption(group: OptionGroup, option: FontOption): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定删除字体“${option.name || '未命名字体'}”吗？已被题目使用的题目会变为待修复状态。`, '删除字体', {
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
    await ElMessageBox.confirm(`确定删除空分区“${group.name || '未命名分区'}”吗？`, '删除分区', {
      confirmButtonText: '删除分区', cancelButtonText: '取消', type: 'warning',
    });
    groups.value.splice(groups.value.indexOf(group), 1);
  } catch { /* 用户取消时不改变内容。 */ }
}

function dragStart(group: OptionGroup, index: number): void {
  dragged.value = { group, index };
}

function dropOption(group: OptionGroup, index: number): void {
  if (!dragged.value || dragged.value.group !== group || dragged.value.index === index) return;
  const [option] = group.options.splice(dragged.value.index, 1);
  group.options.splice(index, 0, option);
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
        <div><p class="eyebrow">题库设置</p><h1 id="font-options-title" class="page-title">字体快捷项</h1><p class="page-description">拖动字体调整显示顺序；保存后答题端与新增题目立即同步。</p></div>
        <button type="button" class="secondary" @click="addGroup">添加分区</button>
      </header>
      <div v-if="loading" class="loading card">正在读取字体快捷项…</div>
      <ErrorPanel v-else-if="error && !groups.length" :message="error" @retry="load" />
      <form v-else class="catalog" @submit.prevent="save">
        <article v-for="(group, groupIndex) in groups" :key="group.id || `new-${groupIndex}`" class="group-card card">
          <header class="group-header"><label>分区名称<input v-model="group.name" maxlength="100" placeholder="例如：类黑体" /></label><button type="button" class="text-danger" @click="removeGroup(group)">删除分区</button></header>
          <div class="option-list"><div v-for="(option, optionIndex) in group.options" :key="option.id || `new-${optionIndex}`" class="option-row" draggable="true" @dragstart="dragStart(group, optionIndex)" @dragover.prevent @drop="dropOption(group, optionIndex)"><span class="drag-mark" title="拖动调整顺序">⠿</span><input v-model="option.name" maxlength="500" placeholder="字体名称，例如：黑体" /><label class="difficulty-label">最低难度<select v-model.number="option.minimumDifficulty"><option v-for="star in 3" :key="star" :value="star">{{ star }} 星</option></select></label><button type="button" class="remove-option" :aria-label="`删除 ${option.name || '该字体'}`" @click="removeOption(group, option)">×</button></div></div>
          <button type="button" class="add-option" @click="addOption(group)">＋ 添加字体</button>
        </article>
        <p v-if="error" class="status-error" role="alert">{{ error }}</p>
        <footer class="save-bar"><p>删除字体需确认；只有空分区才能删除。</p><button type="submit" class="save" :disabled="saving">{{ saving ? '正在保存…' : '保存字体快捷项' }}</button></footer>
      </form>
    </section>
  </AdminShell>
</template>

<style scoped>
.admin-content { width: min(820px, calc(100% - 64px)); margin: 0 auto; padding: 42px 0 56px; }.page-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; margin-bottom: 20px; }.page-description { margin-bottom: 0; }.loading { padding: 22px; }.catalog { display: grid; gap: 12px; }.group-card { display: grid; grid-template-columns: 172px minmax(0, 1fr); padding: 0; overflow: hidden; }.group-header { display: flex; flex-direction: column; justify-content: space-between; gap: 14px; padding: 16px; border-right: 1px solid #efdbc1; background: var(--color-surface-accent); }.group-header label, .difficulty-label { display: grid; gap: 5px; color: var(--color-text-muted); font-size: 12px; font-weight: 750; }.group-header input { width: 100%; border: 0; border-bottom: 1px solid #d8b789; padding: 5px 0; color: var(--color-text); background: transparent; font-size: 16px; font-weight: 750; }.option-list { display: grid; padding: 2px 16px; }.option-row { display: grid; grid-template-columns: 20px minmax(0, 1fr) 104px 26px; align-items: end; gap: 8px; padding: 8px 0; border-bottom: 1px solid var(--color-border); }.option-row[draggable=true] { cursor: grab; }.option-row:active { cursor: grabbing; }.drag-mark { display: grid; width: 20px; height: 30px; place-items: center; color: #9a652d; font-size: 17px; line-height: 1; }.option-row > input, select { min-height: 34px; border: 1px solid var(--color-border); border-radius: 8px; padding: 0 9px; color: var(--color-text); background: var(--color-surface-warm); }.remove-option, .text-danger { border: 0; background: transparent; color: var(--color-danger); font-weight: 700; }.text-danger { align-self: flex-start; padding: 5px 0; }.remove-option { width: 26px; height: 26px; border-radius: 50%; font-size: 19px; }.remove-option:hover, .text-danger:hover { background: #fff0ee; }.add-option { justify-self: start; margin: 10px 16px 12px; border: 1px dashed #d7aa73; border-radius: 8px; padding: 6px 10px; color: #93551e; background: #fffaf2; font-size: 13px; font-weight: 700; }.secondary { min-height: 38px; border: 1px solid var(--color-border); border-radius: 9px; padding: 0 12px; color: var(--color-text); background: #fff; font-weight: 700; }.save-bar { display: flex; align-items: center; justify-content: space-between; gap: 18px; padding: 14px 18px; border: 1px solid #efdbc1; border-radius: 14px; background: #fff8ed; }.save-bar p { margin: 0; color: var(--color-text-muted); font-size: 13px; }.save { min-height: 42px; flex: none; border: 0; border-radius: var(--radius-button); padding: 0 18px; color: #fff; background: var(--color-action); font-weight: 750; }.save:disabled { opacity: .65; }
@media (max-width: 760px) { .admin-content { width: min(100% - 32px, 820px); padding-top: 28px; }.page-header, .save-bar { align-items: flex-start; flex-direction: column; }.group-card { grid-template-columns: 1fr; }.group-header { gap: 10px; border-right: 0; border-bottom: 1px solid #efdbc1; }.option-row { grid-template-columns: 20px minmax(0, 1fr) 26px; }.difficulty-label { grid-column: 2; }.save-bar .save { width: 100%; } }
</style>
