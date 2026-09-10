<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { onBeforeRouteLeave } from 'vue-router';
import { ElMessageBox } from 'element-plus';
import { api, ApiError } from '@/api/client';
import type { OptionGroup } from '@/types';
import BatchCropCanvas from '@/components/BatchCropCanvas.vue';
import { addPage, cropImage, decodeImage, deleteDraft, invalidateRegion, isFrozen, listDrafts, readImage, regionProblem, saveDraft, thumbnail,
  matchesReviewFilter, type BatchDraft, type BatchPage, type BatchRegion, type BatchReviewFilter, type Rect } from '@/lib/batchDrafts';

const props = defineProps<{ username: string }>();
const draft = ref<BatchDraft>();
const drafts = ref<BatchDraft[]>([]);
const groups = ref<OptionGroup[]>([]);
const error = ref('');
const storageError = ref('');
const saveStatus = ref('');
const loading = ref(true);
const importing = ref(false);
const importProgress = ref('');
const processing = ref(false);
const submitting = ref(false);
const pauseRequested = ref(false);
const submitProgress = ref('');
const search = ref('');
const source = ref('');
const explanationSuggestion = ref('');
const review = ref(false);
const reviewFilter = ref<BatchReviewFilter>('all');
const selectedForSubmit = ref<string[]>([]);
const pagesOpen = ref(false);
const mobilePanel = ref('canvas');
const canvas = ref<InstanceType<typeof BatchCropCanvas>>();
const input = ref<HTMLInputElement>();
const busy = computed(() => processing.value || submitting.value);
const currentPage = computed(() => draft.value?.pages.find((page) => page.id === draft.value?.pageId));
const currentRegion = computed(() => currentPage.value?.regions.find((region) => region.id === draft.value?.regionId));
const options = computed(() => groups.value.flatMap((group) => group.options));
const filteredGroups = computed(() => groups.value.map((group) => ({ ...group, options: group.options.filter((option) => option.name.toLowerCase().includes(search.value.trim().toLowerCase())) })).filter((group) => group.options.length));
const entries = computed(() => draft.value?.pages.flatMap((page, pageIndex) => page.regions.map((region, regionIndex) => ({ page, pageIndex, region, regionIndex }))) ?? []);
const candidates = computed(() => entries.value.filter(({ region }) => region.status === 'ready' || region.status === 'pending'));
const filteredEntries = computed(() => entries.value.filter(({ region }) => matchesReviewFilter(region.status, reviewFilter.value)));
const filteredCandidates = computed(() => filteredEntries.value.filter(({ region }) => region.status === 'ready' || region.status === 'pending'));
const reviewFilterOptions = computed(() => [
  { value: 'all' as const, label: '全部', count: entries.value.length },
  { value: 'saved' as const, label: '已入库', count: entries.value.filter(({ region }) => region.status === 'saved').length },
  { value: 'pending' as const, label: '待入库', count: entries.value.filter(({ region }) => region.status === 'ready' || region.status === 'pending').length },
  { value: 'draft' as const, label: '待补充', count: entries.value.filter(({ region }) => region.status === 'draft').length },
  { value: 'deleted' as const, label: '已删除', count: entries.value.filter(({ region }) => region.status === 'deleted').length },
]);
const draftCount = computed(() => entries.value.filter(({ region }) => region.status === 'draft').length);
const savedCount = computed(() => entries.value.filter(({ region }) => region.status === 'saved').length);
const pendingCount = computed(() => entries.value.filter(({ region }) => region.status === 'ready' || region.status === 'pending').length);
const allVisibleSelected = computed(() => filteredCandidates.value.length > 0 && filteredCandidates.value.every(({ region }) => selectedForSubmit.value.includes(region.id)));
const frozen = computed(() => !!currentRegion.value && isFrozen(currentRegion.value));
let revision = 0;
let savedRevision = 0;
let saveTimer: ReturnType<typeof setTimeout> | undefined;
let saveQueue: Promise<unknown> = Promise.resolve();
let releaseLock: (() => void) | undefined;
let sourceVersion = 0;
let disposed = false;
const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T;
const message = (caught: unknown) => caught instanceof Error ? caught.message : '操作失败，请重试';

watch(draft, () => {
  if (!draft.value) return;
  revision++;
  saveStatus.value = '正在保存到本机…';
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => { void persist(); }, 400);
}, { deep: true, flush: 'sync' });

async function persist(write: (snapshot: BatchDraft) => Promise<unknown> = saveDraft): Promise<boolean> {
  clearTimeout(saveTimer);
  if (!draft.value) return true;
  const snapshot = clone(draft.value);
  snapshot.updatedAt = Date.now();
  const version = revision;
  const operation = saveQueue.catch(() => undefined).then(() => write(snapshot));
  saveQueue = operation;
  try {
    await operation;
    savedRevision = Math.max(savedRevision, version);
    if (revision === version) { saveStatus.value = '已保存到本机'; storageError.value = ''; }
    return true;
  } catch (caught) {
    storageError.value = `尚未保存到本机：${message(caught)}。请勿关闭页面，释放浏览器存储空间后重试。`;
    saveStatus.value = '本机保存失败';
    return false;
  }
}

async function acquire(id: string): Promise<boolean> {
  if (!navigator.locks) { error.value = '此浏览器无法保护草稿免于多标签页覆盖，请使用新版 Chrome、Edge 或 Safari。'; return false; }
  return new Promise((resolve) => {
    void navigator.locks.request(`mikanquiz-batch:${id}`, { ifAvailable: true }, async (lock) => {
      if (!lock) { error.value = '此批次正在另一个标签页编辑，请关闭该页面后重试。'; resolve(false); return; }
      await new Promise<void>((release) => { releaseLock = release; resolve(true); });
    }).catch((caught) => { error.value = message(caught); resolve(false); });
  });
}

async function refreshList() { drafts.value = await listDrafts(props.username); }
async function openBatch(id: string) {
  error.value = '';
  if (!await acquire(id)) return;
  try {
    const value = (await listDrafts(props.username)).find((item) => item.id === id);
    if (!value) throw new Error('此批次已不存在');
    revision = savedRevision = 0;
    draft.value = value;
    review.value = false;
    saveStatus.value = '已保存到本机';
  } catch (caught) { releaseLock?.(); releaseLock = undefined; error.value = message(caught); }
}
async function newBatch() {
  try {
    const { value } = await ElMessageBox.prompt('为这批漫画起一个名字，之后可在本机继续。', '新建批次', {
      inputValue: `漫画制题 ${new Date().toLocaleDateString('zh-CN')}`, inputValidator: (value) => !!value?.trim() && value.length <= 100 || '请输入 1–100 字的批次名',
      confirmButtonText: '创建', cancelButtonText: '取消',
    });
    const item: BatchDraft = { id: crypto.randomUUID(), owner: props.username, name: value.trim(), updatedAt: Date.now(), defaultDifficulty: 2, pageId: '', regionId: '', pages: [] };
    await saveDraft(item);
    await openBatch(item.id);
    void navigator.storage?.persist?.().catch(() => undefined);
  } catch (caught) { if (caught !== 'cancel' && caught !== 'close') error.value = message(caught); }
}
async function backToBatches() {
  if (busy.value || importing.value || !await persist()) return;
  releaseLock?.(); releaseLock = undefined;
  draft.value = undefined;
  review.value = false;
  clearTimeout(saveTimer);
  await refreshList();
}
async function removeBatch(item: BatchDraft) {
  try {
    await ElMessageBox.confirm(`删除「${item.name}」的本机原图和草稿？已入库题目不受影响。`, '删除本机批次', { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' });
    if (!await acquire(item.id)) return;
    try { await deleteDraft(item); } finally { releaseLock?.(); releaseLock = undefined; }
    await refreshList();
  } catch (caught) { if (caught !== 'cancel' && caught !== 'close') error.value = message(caught); }
}

async function importFiles(files: File[]) {
  if (!draft.value || importing.value || busy.value) return;
  importing.value = true;
  error.value = '';
  const failures: string[] = [];
  const sorted = files.sort((a, b) => a.name.localeCompare(b.name, 'zh-CN', { numeric: true }));
  for (const [index, file] of sorted.entries()) {
    if (disposed) break;
    importProgress.value = `正在读取 ${index + 1} / ${sorted.length}：${file.name}`;
    try {
      if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) throw new Error('仅支持 JPG、PNG、WebP');
      const image = await decodeImage(file);
      const page: BatchPage = { id: crypto.randomUUID(), name: file.name, width: image.naturalWidth, height: image.naturalHeight,
        thumbnail: thumbnail(image, image.naturalWidth, image.naturalHeight), checked: false, regions: [] };
      if (!page.width || !page.height) throw new Error('图片没有有效尺寸');
      draft.value.pages.push(page);
      if (!draft.value.pageId) draft.value.pageId = page.id;
      if (!await persist((snapshot) => addPage(snapshot, page, file))) {
        draft.value.pages = draft.value.pages.filter((item) => item.id !== page.id);
        if (draft.value.pageId === page.id) draft.value.pageId = draft.value.pages[0]?.id ?? '';
        // Do not let the automatic save hide a failed original-image write.
        clearTimeout(saveTimer);
        failures.push(`${file.name}：原图未保存，请释放空间后重新添加`);
        break;
      }
    } catch (caught) { failures.push(`${file.name}：${message(caught)}`); }
  }
  importing.value = false;
  importProgress.value = '';
  if (failures.length) error.value = failures.join('；');
}
function fileChange(event: Event) {
  const target = event.target as HTMLInputElement;
  void importFiles(Array.from(target.files ?? [])); target.value = '';
}
function drop(event: DragEvent) { event.preventDefault(); void importFiles(Array.from(event.dataTransfer?.files ?? [])); }
function choosePage(page: BatchPage) {
  if (!draft.value || busy.value) return;
  draft.value.pageId = page.id;
  draft.value.regionId = page.regions[0]?.id ?? '';
  pagesOpen.value = false; search.value = ''; void persist();
}
function selectRegion(id: string) { if (draft.value && !busy.value) { draft.value.regionId = id; search.value = ''; void persist(); } }

watch(() => currentPage.value?.id, async (id) => {
  const version = ++sourceVersion;
  if (source.value) URL.revokeObjectURL(source.value);
  source.value = '';
  if (!id) return;
  try {
    // New pages become visible only after their image transaction finishes.
    await saveQueue.catch(() => undefined);
    const blob = await readImage(id);
    if (version !== sourceVersion || disposed) return;
    if (!blob) throw new Error('本机原图未找到，请重新添加该图片');
    source.value = URL.createObjectURL(blob);
  } catch (caught) { error.value = message(caught); }
});

function createRegion(rect: Rect) {
  if (!draft.value || !currentPage.value || busy.value) return;
  const region: BatchRegion = { ...rect, id: crypto.randomUUID(), status: 'draft', form: {
    text: '请选择以下日文对应的汉字字体', imageUrl: null, difficulty: draft.value.defaultDifficulty, correctOptionId: '', explanation: '',
  } };
  currentPage.value.regions.push(region);
  draft.value.regionId = region.id;
  currentPage.value.checked = false;
  search.value = '';
  void persist();
}
function changeRegion(id: string, rect: Rect) {
  const region = currentPage.value?.regions.find((item) => item.id === id);
  if (!region || isFrozen(region) || busy.value) return;
  if (region.x === rect.x && region.y === rect.y && region.width === rect.width && region.height === rect.height) return;
  Object.assign(region, rect); invalidateRegion(region); void persist();
}
function editRegion() { if (currentRegion.value) invalidateRegion(currentRegion.value); }
function previousExplanation(region: BatchRegion): string {
  if (!region.form.correctOptionId) return '';
  const currentIndex = entries.value.findIndex(({ region: item }) => item.id === region.id);
  for (let index = currentIndex - 1; index >= 0; index--) {
    const previous = entries.value[index].region;
    if (previous.form.correctOptionId === region.form.correctOptionId && previous.form.explanation.trim()) return previous.form.explanation.trim();
  }
  return '';
}
function refreshExplanationSuggestion(): void {
  const region = currentRegion.value;
  explanationSuggestion.value = region && !region.form.explanation.trim() ? previousExplanation(region) : '';
}
function fontSelected(optionId: string): void {
  const region = currentRegion.value;
  if (!region || isFrozen(region)) return;
  region.form.correctOptionId = optionId;
  editRegion();
  refreshExplanationSuggestion();
  void persist();
}
function explanationInput(): void {
  if (currentRegion.value?.form.explanation.trim()) explanationSuggestion.value = '';
}
function acceptExplanationSuggestion(event: KeyboardEvent): void {
  const region = currentRegion.value;
  if (!region || isFrozen(region) || !explanationSuggestion.value) return;
  event.preventDefault();
  region.form.explanation = explanationSuggestion.value;
  explanationSuggestion.value = '';
  editRegion();
  void persist();
}
watch(() => [currentRegion.value?.id, currentRegion.value?.form.correctOptionId], refreshExplanationSuggestion, { immediate: true });
function previewGroups(region: BatchRegion): OptionGroup[] {
  return groups.value.map((group) => ({ ...group, options: group.options.filter((option) => option.minimumDifficulty <= region.form.difficulty) })).filter((group) => group.options.length);
}
async function completeRegion() {
  const region = currentRegion.value; const page = currentPage.value;
  if (!region || !page || isFrozen(region) || busy.value) return;
  region.error = regionProblem(region, options.value);
  if (region.error) return;
  processing.value = true;
  try {
    const crop = await cropImage(page, region);
    region.preview = crop.preview;
    region.status = 'ready';
    if (await persist()) { draft.value!.regionId = ''; mobilePanel.value = 'canvas'; await nextTick(); canvas.value?.focusCanvas(); }
  } catch (caught) { region.error = message(caught); }
  finally { processing.value = false; }
}
function leaveForLater() { if (draft.value) { draft.value.regionId = ''; mobilePanel.value = 'canvas'; void persist(); canvas.value?.focusCanvas(); } }
function deleteRegion() {
  const page = currentPage.value; const region = currentRegion.value;
  if (!page || !region || isFrozen(region) || busy.value) return;
  page.regions.splice(page.regions.indexOf(region), 1); draft.value!.regionId = ''; void persist();
}
function label(region: BatchRegion) {
  return ({ draft: '待补充', ready: '已完成', pending: '待确认提交', saved: '已入库', deleted: '入库后已删除' })[region.status];
}
function fontName(id: string) { return options.value.find((option) => option.id === id)?.name ?? '未选择／字体已移除'; }
async function openReview() {
  if (busy.value || importing.value || !await persist()) return;
  try {
    groups.value = await api.getOptionGroups();
    candidates.value.forEach(({ region }) => {
      if (region.status === 'ready') { const problem = regionProblem(region, options.value); if (problem) { region.status = 'draft'; region.error = problem; } }
    });
    selectedForSubmit.value = candidates.value.map(({ region }) => region.id);
    reviewFilter.value = 'all';
    review.value = true;
  } catch (caught) { error.value = message(caught); }
}
function toggleVisibleSelection(event: Event): void {
  const checked = (event.target as HTMLInputElement).checked;
  const visibleIds = new Set(filteredCandidates.value.map(({ region }) => region.id));
  selectedForSubmit.value = checked
    ? Array.from(new Set([...selectedForSubmit.value, ...visibleIds]))
    : selectedForSubmit.value.filter((id) => !visibleIds.has(id));
}
function reviewEdit(page: BatchPage, region: BatchRegion) { review.value = false; choosePage(page); selectRegion(region.id); mobilePanel.value = 'editor'; }
async function submit() {
  if (submitting.value || !selectedForSubmit.value.length || !await persist()) return;
  submitting.value = true; pauseRequested.value = false; error.value = '';
  try {
    const session = await api.getAdminSession();
    if (session.username !== props.username) throw new Error('管理员账号已改变，请返回批次列表并重新登录原账号');
    const selected = candidates.value.filter(({ region }) => selectedForSubmit.value.includes(region.id));
    for (const [index, { page, region }] of selected.entries()) {
      if (pauseRequested.value) break;
      submitProgress.value = `正在提交 ${index + 1} / ${selected.length}`;
      try {
        region.error = '';
        if (!region.request) {
          const problem = regionProblem(region, options.value);
          if (problem) { region.status = 'draft'; throw new Error(problem); }
          if (!region.uploadUrl) {
            const crop = await cropImage(page, region);
            region.uploadUrl = await api.uploadImage(crop.file);
            if (!await persist()) break;
          }
          region.request = { id: crypto.randomUUID(), payload: { ...clone(region.form), imageUrl: region.uploadUrl } };
          region.status = 'pending';
          // Persist the exact request BEFORE sending: a lost response must replay identical content.
          if (!await persist()) break;
        }
        const question = await api.createQuestion(region.request.payload, region.request.id);
        region.questionId = question.id; region.status = 'saved'; region.error = '';
      } catch (caught) {
        region.error = message(caught);
        if (caught instanceof ApiError) {
          if (caught.status === 422 || caught.status === 400) { region.status = 'draft'; delete region.request; }
          if (caught.code === 'QUESTION_REQUEST_DELETED') region.status = 'deleted';
          if (caught.status === 401 || caught.status === 403) { pauseRequested.value = true; error.value = '登录已过期，请在新标签页登录同一账号，再回来重试；本机草稿已保留。'; }
        }
      }
      if (!await persist()) break;
    }
    selectedForSubmit.value = candidates.value.map(({ region }) => region.id);
    submitProgress.value = pauseRequested.value ? '已暂停，剩余题目已保留' : '本次提交结束，请查看逐题结果';
  } catch (caught) { error.value = message(caught); }
  finally { submitting.value = false; }
}
function shortcut(event: KeyboardEvent) {
  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter' && !review.value) { event.preventDefault(); void completeRegion(); }
}
function beforeUnload(event: BeforeUnloadEvent) {
  if (importing.value || busy.value || revision !== savedRevision) { event.preventDefault(); event.returnValue = ''; }
}
onBeforeRouteLeave(async () => { if (importing.value || busy.value) { error.value = '请等待当前操作完成，或暂停提交后再离开。'; return false; } return await persist(); });
onMounted(async () => {
  window.addEventListener('beforeunload', beforeUnload);
  try { await Promise.all([refreshList(), api.getOptionGroups().then((value) => { groups.value = value; })]); }
  catch (caught) { error.value = message(caught); }
  finally { loading.value = false; }
});
onBeforeUnmount(() => {
  disposed = true; sourceVersion++; clearTimeout(saveTimer); releaseLock?.();
  if (source.value) URL.revokeObjectURL(source.value);
  window.removeEventListener('beforeunload', beforeUnload);
});
</script>

<template>
  <section class="batch-workspace" @keydown="shortcut">
    <header class="batch-header">
      <div class="heading-main"><RouterLink to="/admin/questions" class="back-link">← 题库</RouterLink><span class="heading-divider">/</span><h1>批量制题</h1><template v-if="draft"><span class="heading-divider">/</span><span class="batch-name">{{ draft.name }}</span></template></div>
      <div class="header-actions"><span v-if="draft" class="save-status" role="status">{{ saveStatus }}</span><button v-if="draft" :disabled="busy || importing" @click="backToBatches">切换批次</button><button v-if="draft && !review" class="primary" :disabled="busy || importing || !entries.length" @click="openReview">检查并入库 · {{ candidates.length }}</button></div>
    </header>
    <div v-if="error" class="notice danger" role="alert">{{ error }} <button @click="error = ''">收起提示</button><a href="/admin/login" target="_blank" rel="noopener">登录页面 ↗</a></div>
    <div v-if="storageError" class="notice danger" role="alert">{{ storageError }} <button @click="persist()">重试本机保存</button></div>
    <p v-if="importProgress" class="notice" role="status">{{ importProgress }}</p>
    <div v-if="loading" class="welcome">正在读取本机批次…</div>
    <div v-else-if="!draft" class="batch-home">
      <p class="eyebrow">从漫画整页，连续制作题目</p><h2>选好区域，再专心判断字体。</h2><p class="muted">一次添加多页图片，框选题图并填写答案。未完成内容留在这台电脑，准备好的题目随时入库。</p><button class="primary new-batch" @click="newBatch">＋ 新建批次</button>
      <div class="batch-list"><article v-for="(item, index) in drafts" :key="item.id"><div><h3>{{ item.name }}</h3><p class="muted">{{ item.pages.length }} 页 · {{ item.pages.reduce((n, page) => n + page.regions.length, 0) }} 个区域 · {{ new Date(item.updatedAt).toLocaleString('zh-CN') }}</p></div><div><button class="primary" @click="openBatch(item.id)">{{ index === 0 ? '继续上次制题' : '继续制题' }}</button><button class="danger-link" @click="removeBatch(item)">删除</button></div></article></div>
      <p class="local-note">草稿仅保存在当前账号、当前浏览器。清除网站数据会删除本机草稿；已入库题目不受影响。</p>
    </div>
    <template v-else-if="review">
      <section class="review-view">
        <div class="review-heading"><div><h2>检查并入库</h2><p class="muted">已入库 {{ savedCount }} 题 · 待入库 {{ pendingCount }} 题 · 待补充 {{ draftCount }} 题。下面按答题端样式检查题干、题图、选项和解析。</p></div><button :disabled="submitting" @click="review = false">← 继续框选</button></div>
        <div class="review-filter"><label for="review-status-filter">题目状态</label><select id="review-status-filter" v-model="reviewFilter" :disabled="submitting"><option v-for="option in reviewFilterOptions" :key="option.value" :value="option.value">{{ option.label }} · {{ option.count }}</option></select><span>显示 {{ filteredEntries.length }} / {{ entries.length }} 题</span></div>
        <div class="review-actions"><label :class="{ disabled: !filteredCandidates.length }"><input type="checkbox" :disabled="submitting || !filteredCandidates.length" :checked="allVisibleSelected" @change="toggleVisibleSelection" />{{ reviewFilter === 'all' ? '选择全部可提交题目' : '选择当前筛选中的可提交题目' }}</label><span role="status">{{ submitProgress }}</span><button v-if="submitting" @click="pauseRequested = true">{{ pauseRequested ? '等待当前题完成…' : '暂停提交' }}</button><button v-else class="primary" :disabled="!selectedForSubmit.length" @click="submit">入库／重试 {{ selectedForSubmit.length }} 题</button></div>
        <article v-for="entry in filteredEntries" :key="entry.region.id" class="review-row">
          <input v-if="['ready','pending'].includes(entry.region.status)" v-model="selectedForSubmit" :disabled="submitting" type="checkbox" :value="entry.region.id" :aria-label="'选择第 ' + (entry.pageIndex + 1) + ' 页区域 ' + (entry.regionIndex + 1)" />
          <span v-else class="checkbox-space"></span>
          <div class="review-preview">
            <div class="review-preview-media"><img v-if="entry.region.preview" :src="entry.region.preview" alt="题图预览" /><span v-else>区域尚未完成</span></div>
            <div class="review-preview-body">
              <div class="review-preview-meta">第 {{ entry.pageIndex + 1 }} 页 · 区域 {{ entry.regionIndex + 1 }} · {{ '★'.repeat(entry.region.form.difficulty) }} · {{ fontName(entry.region.form.correctOptionId) }}</div>
              <h3>{{ entry.region.form.text }}</h3>
              <div class="review-preview-options" aria-label="题目选项">
                <section v-for="group in previewGroups(entry.region)" :key="group.id" class="review-preview-group">
                  <span class="preview-group-label">{{ group.name }}</span>
                  <span v-for="option in group.options" :key="option.id" class="preview-option" :class="{ correct: option.id === entry.region.form.correctOptionId }">{{ option.name }}</span>
                </section>
              </div>
              <p class="review-explanation"><strong>解析</strong> {{ entry.region.form.explanation || '尚未填写解析' }}</p>
              <p v-if="entry.region.error" class="error-text" role="alert">{{ entry.region.error }}</p>
            </div>
          </div>
          <div class="review-row-actions"><span class="status-tag" :class="entry.region.status">{{ label(entry.region) }}</span><RouterLink v-if="entry.region.questionId" :to="'/admin/questions/' + entry.region.questionId + '/edit'">题库编辑 ↗</RouterLink><button v-else :disabled="submitting" @click="reviewEdit(entry.page, entry.region)">{{ entry.region.status === 'draft' ? '回到框选' : '编辑区域' }}</button></div>
        </article>
        <div v-if="!filteredEntries.length" class="review-empty">当前筛选没有题目。</div>
      </section>
    </template>
    <template v-else>
      <input ref="input" type="file" multiple accept="image/jpeg,image/png,image/webp" hidden @change="fileChange" />
      <div class="mobile-tools"><button @click="pagesOpen = !pagesOpen">页面 · {{ draft.pages.length }}</button><button :aria-pressed="mobilePanel === 'canvas'" @click="mobilePanel = 'canvas'">漫画</button><button :aria-pressed="mobilePanel === 'editor'" @click="mobilePanel = 'editor'">当前题目</button></div>
      <div class="workbench" @dragover.prevent @drop="drop">
        <aside class="page-rail" :class="{ open: pagesOpen }"><div class="rail-heading"><strong>页面 · {{ draft.pages.length }}</strong><button :disabled="importing || busy" @click="input?.click()">＋ 添加</button></div><div class="page-list"><button v-for="(page, index) in draft.pages" :key="page.id" :class="['page-item', { active: page.id === draft.pageId }]" :disabled="busy" @click="choosePage(page)"><img :src="page.thumbnail" alt="" loading="lazy" /><strong>{{ String(index + 1).padStart(2, '0') }} · {{ page.name }}</strong><small>{{ page.regions.filter(region => region.status === 'ready' || region.status === 'saved').length }} 已完成 · {{ page.checked ? '已检查' : '未标记检查' }}</small></button></div></aside>
        <main class="image-area" :class="{ 'mobile-hidden': mobilePanel !== 'canvas' }">
          <template v-if="currentPage"><BatchCropCanvas v-if="source" ref="canvas" :page="currentPage" :source="source" :selected="draft.regionId" :disabled="busy" @create="createRegion" @select="selectRegion" @change="changeRegion"><template #toolbar-leading><strong class="toolbar-page-name">{{ currentPage.name }}</strong></template><template #toolbar-trailing><label class="toolbar-page-check"><input v-model="currentPage.checked" type="checkbox" :disabled="busy" @change="persist()" />此页已检查</label></template></BatchCropCanvas><div v-else class="welcome">正在读取原图…</div></template>
          <div v-else class="import-empty"><span class="empty-marker">＋</span><h2>把漫画图片拖到这里</h2><p>支持 JPG、PNG、WebP，可一次选择多页</p><button class="primary" :disabled="importing" @click="input?.click()">选择图片</button><small>原图保存在本机，入库时只上传裁图。</small></div>
        </main>
        <aside class="region-editor" :class="{ 'mobile-hidden': mobilePanel !== 'editor' }">
          <template v-if="currentRegion && currentPage">
            <header class="editor-heading"><span class="eyebrow">当前题目</span><h2>区域 {{ currentPage.regions.indexOf(currentRegion) + 1 }}</h2></header>
            <div class="editor-scroll">
              <fieldset :disabled="frozen || busy" @input="editRegion" @change="editRegion">
                <label class="field">难度<select v-model.number="currentRegion.form.difficulty"><option v-for="star in 3" :key="star" :value="star">{{ '★'.repeat(star) }}</option></select></label>
                <div class="field"><span>正确字体 <strong v-if="currentRegion.form.correctOptionId">· {{ fontName(currentRegion.form.correctOptionId) }}</strong></span><input v-model="search" type="search" placeholder="搜索字体名称" aria-label="搜索字体名称" @input.stop @change.stop /></div>
                <div class="font-groups"><section v-for="group in filteredGroups" :key="group.id"><h3>{{ group.name }}</h3><div class="font-options"><label v-for="option in group.options" :key="option.id" :class="{ chosen: currentRegion.form.correctOptionId === option.id, locked: option.minimumDifficulty > currentRegion.form.difficulty }"><input v-model="currentRegion.form.correctOptionId" type="radio" name="batch-font" :value="option.id" :disabled="option.minimumDifficulty > currentRegion.form.difficulty" @change="fontSelected(option.id)" />{{ option.name }}<small v-if="option.minimumDifficulty > currentRegion.form.difficulty">{{ option.minimumDifficulty }}★起</small></label></div></section><p v-if="!filteredGroups.length" class="muted">没有匹配的字体</p></div>
                <label class="field"><span>解析</span><textarea v-model="currentRegion.form.explanation" maxlength="1000" rows="4" :placeholder="explanationSuggestion || '写下判别依据或补充说明'" @input="explanationInput" @keydown.tab="acceptExplanationSuggestion" /><small v-if="explanationSuggestion" class="explanation-suggestion" role="status">已有同字体解析，按 <kbd>Tab</kbd> 采用</small></label>
                <details><summary>题干</summary><label class="field"><span class="sr-only">题干</span><textarea v-model="currentRegion.form.text" maxlength="500" rows="2" /></label></details>
              </fieldset>
              <p v-if="currentRegion.error" class="error-text" role="alert">{{ currentRegion.error }}</p>
              <p v-if="currentRegion.status === 'pending'" class="notice">提交结果待确认，内容已锁定。请在检查页重试原请求。</p>
              <RouterLink v-if="currentRegion.questionId" :to="'/admin/questions/' + currentRegion.questionId + '/edit'">打开题库编辑 ↗</RouterLink>
            </div>
            <footer v-if="!frozen" class="editor-footer"><button class="primary" :disabled="busy" @click="completeRegion">{{ processing ? '正在准备裁图…' : '完成并继续' }}</button><small>Ctrl / ⌘ + Enter</small><div><button :disabled="busy" @click="leaveForLater">暂留待补</button><button class="danger-link" :disabled="busy" @click="deleteRegion">删除区域</button></div></footer>
          </template>
          <div v-else class="editor-empty"><span class="eyebrow">一框一道题</span><h2>在漫画上框出<br />下一处字体。</h2><p>框选后在这里选择正确字体、填写解析。遇到不确定的区域，可以先留待补充。</p><label class="field">新题默认难度<select v-model.number="draft.defaultDifficulty"><option v-for="star in 3" :key="star" :value="star">{{ '★'.repeat(star) }}</option></select></label><small>仅作用于之后新建的区域</small><p class="local-note">草稿仅在此浏览器保存</p></div>
        </aside>
      </div>
    </template>
  </section>
</template>

<style scoped>
.batch-workspace{height:100vh;display:flex;flex-direction:column;color:var(--color-text);background:var(--color-bg);font-size:13px}.batch-header{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:16px 24px;border-bottom:1px solid var(--color-border);background:var(--color-surface)}.heading-main,.header-actions{display:flex;align-items:center;gap:12px;min-width:0}.heading-main h1{font-size:18px;white-space:nowrap;margin:0}.heading-divider{color:var(--color-border)}.batch-name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:260px}.back-link,a{color:var(--color-action)}.save-status{color:var(--color-text-muted);font-size:12px;white-space:nowrap}button{min-height:34px;padding:6px 11px;border:1px solid var(--color-border);border-radius:8px;background:var(--color-surface);color:var(--color-text);font:inherit;cursor:pointer}button:hover:not(:disabled){border-color:var(--color-action);background:var(--color-surface-warm)}button.primary{background:var(--color-action);border-color:var(--color-action);color:white;font-weight:700}button:disabled{opacity:.5;cursor:default}button[aria-pressed=true]{background:var(--color-surface-accent);border-color:var(--color-action)}.danger-link{color:var(--color-danger);border-color:transparent;background:transparent}button:focus-visible,a:focus-visible,input:focus-visible,textarea:focus-visible,select:focus-visible{outline:2px solid var(--color-action);outline-offset:2px}.muted,.local-note{color:var(--color-text-muted)}.notice{margin:0;padding:10px 20px;background:var(--color-surface-accent);font-size:12px;overflow-wrap:anywhere}.notice button,.notice a{margin-left:12px}.danger,.error-text{color:var(--color-danger)}.error-text{font-size:12px}.welcome{padding:48px;text-align:center}.batch-home{width:min(900px,100% - 48px);margin:64px auto;overflow:auto}.batch-home h2{font-size:30px;margin:12px 0}.batch-home>.muted{max-width:630px;line-height:1.9}.new-batch{margin:18px 0 32px;min-height:44px}.batch-list{display:grid;gap:12px}.batch-list article{display:flex;justify-content:space-between;gap:20px;align-items:center;padding:20px;background:var(--color-surface);border:1px solid var(--color-border);border-radius:12px}.batch-list h3{margin:0;font-size:16px}.batch-list p{font-size:12px;margin:8px 0 0}.local-note{font-size:12px;line-height:1.7;margin-top:24px}.workbench{flex:1;min-height:0;display:grid;grid-template-columns:160px minmax(0,1fr) 360px}.page-rail{display:flex;flex-direction:column;min-height:0;border-right:1px solid var(--color-border);background:var(--color-surface-warm)}.rail-heading{display:flex;justify-content:space-between;align-items:center;padding:12px 8px;gap:4px}.rail-heading button{font-size:11px;padding:4px 6px}.page-list{flex:1;overflow:auto;padding:0 8px 12px;display:flex;flex-direction:column;gap:10px}.page-item{text-align:left;padding:8px;flex-shrink:0}.page-item img{display:block;width:100%;height:110px;object-fit:contain;background:#e8e7e4;border-radius:4px;margin-bottom:8px}.page-item strong{display:block;font-size:11px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.page-item small{display:block;font-size:10px;margin-top:6px;color:var(--color-text-muted)}.page-item.active{border-color:var(--color-action);background:var(--color-surface-accent)}.page-actions{display:flex;padding:8px 5px;gap:3px;border-top:1px solid var(--color-border)}.page-actions button{font-size:11px;padding:5px 8px}.image-area{min-width:0;min-height:0;display:flex;flex-direction:column}.page-heading{display:flex;justify-content:space-between;align-items:center;padding:12px 16px;background:var(--color-surface);gap:10px}.page-heading strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.page-heading label{white-space:nowrap;font-size:11px;color:var(--color-text-muted)}.region-strip{display:flex;gap:6px;align-items:center;overflow-x:auto;min-height:60px;padding:10px 14px;background:var(--color-surface);border-top:1px solid var(--color-border)}.region-strip>*{flex-shrink:0;font-size:11px}.region-strip>span{color:var(--color-text-muted);margin-right:5px}.region-editor{display:flex;flex-direction:column;min-height:0;border-left:1px solid var(--color-border);background:var(--color-surface)}.editor-heading{padding:16px 20px 10px}.editor-heading h2{font-size:18px;margin:6px 0}.editor-heading small{font-size:11px;color:var(--color-text-muted);font-weight:400;margin-left:6px}.editor-scroll{flex:1;overflow:auto;padding:0 20px 20px}.crop-preview{object-fit:contain;display:block;width:100%;height:180px;border:1px solid var(--color-border);border-radius:8px;background:var(--color-surface-warm)}.crop-size{display:block;margin:5px 0 16px;text-align:right;font-size:10px}fieldset{border:0;margin:0;padding:0;min-width:0}.field{display:grid;gap:7px;margin:12px 0;font-size:12px}.field input,.field select,.field textarea{width:100%;border:1px solid var(--color-border);border-radius:7px;background:var(--color-surface-warm);color:var(--color-text);padding:8px;font:inherit}.field textarea{resize:vertical;min-height:54px}.field strong{color:var(--color-action);font-weight:600}.font-groups{max-height:250px;overflow:auto;margin-bottom:16px}.font-groups h3{font-size:11px;color:var(--color-text-muted);margin:10px 0 7px}.font-options{display:flex;flex-wrap:wrap;gap:5px}.font-options label{display:flex;align-items:center;gap:4px;border:1px solid var(--color-border);border-radius:7px;padding:6px;font-size:12px;cursor:pointer}.font-options .chosen{border-color:var(--color-action);background:var(--color-surface-accent)}.font-options .locked{opacity:.5}.font-options small{font-size:9px}.font-options input{margin:0;accent-color:var(--color-action)}details summary{cursor:pointer;color:var(--color-text-muted);font-size:12px}.editor-footer{padding:14px 20px;border-top:1px solid var(--color-border)}.editor-footer>.primary{width:100%;min-height:40px}.editor-footer>small{display:block;text-align:center;font-size:10px;color:var(--color-text-muted);margin:6px 0 10px}.editor-footer>div{display:flex;justify-content:space-between}.editor-empty{padding:36px 24px}.editor-empty h2{font-size:23px;line-height:1.6;margin:12px 0}.editor-empty p{color:var(--color-text-muted);line-height:1.9}.editor-empty>small{color:var(--color-text-muted);font-size:11px}.import-empty{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:24px;background:var(--color-surface-warm)}.empty-marker{display:grid;place-items:center;width:60px;height:60px;border:1px dashed var(--color-action);border-radius:14px;color:var(--color-action);font-size:30px}.import-empty h2{font-size:22px;margin:24px 0 0}.import-empty p,.import-empty small{color:var(--color-text-muted);line-height:1.8}.import-empty button{margin:12px 0 18px;min-height:42px}.review-view{padding:24px;overflow:auto;flex:1}.review-heading{display:flex;justify-content:space-between;align-items:center;gap:20px}.review-heading h2{margin:0;font-size:23px}.review-actions{display:flex;align-items:center;gap:20px;padding:16px 0;position:sticky;top:-24px;background:var(--color-bg);z-index:1}.review-actions>span{margin-left:auto;color:var(--color-text-muted);font-size:12px}.review-row{display:flex;gap:16px;align-items:center;padding:16px;background:var(--color-surface);border:1px solid var(--color-border);border-radius:10px;margin-bottom:10px}.checkbox-space{width:13px}.review-image{width:120px;height:80px;flex-shrink:0;padding:4px}.review-image img{width:100%;height:100%;object-fit:contain}.review-info{flex:1;min-width:0}.review-info p{margin:6px 0 0;overflow-wrap:anywhere;white-space:pre-wrap}.review-info strong{font-size:13px}.status-tag{font-size:11px;color:var(--color-text-muted);white-space:nowrap}.status-tag.saved,.status-tag.ready{color:var(--color-success,#39864a)}.status-tag.pending{color:var(--color-action)}.mobile-tools{display:none}.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}
@media(max-width:1199px){.workbench{grid-template-columns:minmax(0,1fr) 340px}.page-rail{display:none}.page-rail.open{display:flex;position:absolute;inset:130px auto 0 0;width:180px;z-index:5;box-shadow:5px 0 15px #0002}.mobile-tools{display:flex;gap:6px;padding:8px 16px;border-bottom:1px solid var(--color-border)}.mobile-tools>button:not(:first-child){display:none}.batch-header{padding:12px 16px}.save-status{display:none}}
@media(max-width:760px){.batch-workspace{height:100dvh}.workbench{display:flex}.image-area,.region-editor{width:100%;flex:1}.mobile-hidden{display:none}.mobile-tools>button:not(:first-child){display:block}.batch-name,.heading-divider{display:none}.batch-header{flex-wrap:wrap;gap:10px}.header-actions{margin-left:auto}.batch-home{margin:28px auto}.batch-home h2{font-size:24px}.batch-list article{flex-direction:column;align-items:flex-start}.review-view{padding:16px}.review-heading,.review-actions{flex-wrap:wrap}.review-row{flex-wrap:wrap;gap:10px}.review-image{width:80px;height:65px}.review-info{min-width:150px}.review-actions{top:-16px}.page-rail.open{top:140px}.region-editor{border-left:0}.notice{max-height:130px;overflow:auto}}

/* Tall manga pages need a scrollable canvas with a useful working height. */
.batch-workspace{height:100vh;height:100dvh;min-height:100dvh;overflow:hidden}
.batch-header{padding:10px 16px}
.workbench{flex:1;min-height:0;overflow:hidden;grid-template-columns:160px minmax(0,1fr) 320px}
.page-rail{overflow:hidden}
.page-list{min-height:0;overflow-x:hidden;overflow-y:auto;scrollbar-gutter:stable}
.page-item img{height:92px}
.rail-heading{padding:8px}
.page-heading{padding:7px 14px}
.editor-heading{padding:10px 14px 6px}
.editor-scroll{padding:0 14px 14px}
.crop-size{margin:0 0 10px}
.field{gap:5px;margin:8px 0}
.font-groups{max-height:220px;margin-bottom:10px}
.editor-footer{padding:10px 14px}
.toolbar-page-name{display:block;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:700}
.toolbar-page-check{display:flex;align-items:center;gap:4px;margin-left:auto;white-space:nowrap;color:var(--color-text-muted);font-size:11px}
.review-view{width:min(1500px,100%);box-sizing:border-box;margin:0 auto}
.review-filter{display:flex;align-items:center;gap:10px;margin-top:20px;color:var(--color-text-muted);font-size:12px}.review-filter label{font-weight:700;color:var(--color-text)}.review-filter select{min-height:34px;border:1px solid var(--color-border);border-radius:8px;padding:0 28px 0 10px;background:var(--color-surface);color:var(--color-text);font:inherit}.review-filter span{font-size:11px}.review-actions label.disabled{color:var(--color-text-muted)}
.review-row{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:start;gap:18px;padding:18px}
.review-preview{display:grid;grid-template-columns:minmax(150px,220px) minmax(0,1fr);gap:18px;min-width:0}
.review-preview-media{display:grid;place-items:center;min-height:150px;padding:10px;border:1px solid var(--color-border);border-radius:10px;background:var(--color-surface-warm)}
.review-preview-media img{display:block;width:100%;height:100%;max-height:180px;object-fit:contain}
.review-preview-media span{color:var(--color-text-muted);font-size:12px;text-align:center}
.review-preview-body{min-width:0}
.review-preview-meta{color:var(--color-text-muted);font-size:11px;line-height:1.5}
.review-preview-body h3{margin:8px 0 12px;font-size:18px;line-height:1.5;overflow-wrap:anywhere}
.review-preview-options{display:grid;gap:8px}
.review-preview-group{display:flex;flex-wrap:wrap;align-items:center;gap:6px}
.preview-group-label{min-width:4em;color:var(--color-text-muted);font-size:11px}
.preview-option{display:inline-flex;align-items:center;gap:5px;padding:4px 8px;border:1px solid var(--color-border);border-radius:6px;font-size:12px}
.preview-option.correct{color:var(--color-action);border-color:var(--color-action);background:var(--color-surface-accent)}
.preview-option small{font-size:10px}
.review-explanation{margin:14px 0 0;line-height:1.7;white-space:pre-wrap;overflow-wrap:anywhere}
.review-row-actions{display:flex;flex-direction:column;align-items:flex-end;gap:10px;min-width:96px}
.review-empty{padding:56px 24px;text-align:center;border:1px dashed var(--color-border);border-radius:10px;color:var(--color-text-muted);background:var(--color-surface)}
.review-row-actions button{white-space:nowrap}
.explanation-suggestion{display:block;padding:8px 10px;border-left:3px solid var(--color-action);background:var(--color-surface-accent);color:var(--color-text-muted);line-height:1.6;overflow-wrap:anywhere}
.explanation-suggestion kbd{padding:1px 4px;border:1px solid var(--color-border);border-radius:4px;background:var(--color-surface);color:var(--color-text);font-size:10px}
@media(max-width:1199px){.workbench{grid-template-columns:minmax(0,1fr) 300px}}
@media(max-width:900px){.review-preview{grid-template-columns:120px minmax(0,1fr)}.review-row-actions{min-width:82px}}
@media(max-width:760px){.batch-workspace{min-height:100dvh}.workbench{min-height:0;overflow:hidden}.toolbar-page-name{max-width:120px}.toolbar-page-check{margin-left:4px}.review-filter{flex-wrap:wrap;margin-top:16px}.review-filter select{flex:1;min-width:150px}.review-filter span{width:100%}.review-row{grid-template-columns:auto minmax(0,1fr);gap:12px}.review-preview{grid-column:2;grid-template-columns:96px minmax(0,1fr);gap:10px}.review-row-actions{grid-column:2;flex-direction:row;justify-content:flex-end;align-items:center;flex-wrap:wrap}.review-preview-media{min-height:100px;padding:6px}.review-preview-body h3{font-size:15px}}
</style>
