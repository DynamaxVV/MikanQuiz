<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue';
import { api } from '@/api/client';
import type { FeedbackContext } from '@/types';

const props = withDefaults(defineProps<{
  source: string;
  context?: FeedbackContext;
}>(), { context: () => ({}) });

const dialog = ref<HTMLDialogElement>();
const open = ref(false);
const message = ref('');
const contactQq = ref('');
const error = ref('');
const submitting = ref(false);
const submitted = ref(false);
const notice = ref('');
const attachments = ref<{ file: File; url: string }[]>([]);
const fileInput = ref<HTMLInputElement>();
const allowedTypes = new Set(['image/jpeg', 'image/png', 'image/webp']);
const maxImageBytes = 3 * 1024 * 1024;

function releaseUrls(): void {
  attachments.value.forEach((item) => URL.revokeObjectURL(item.url));
  attachments.value = [];
}
function resetForm(): void {
  message.value = '';
  contactQq.value = '';
  error.value = '';
  submitted.value = false;
  notice.value = '';
  releaseUrls();
  if (fileInput.value) fileInput.value.value = '';
}
function openDialog(): void {
  resetForm();
  open.value = true;
}
function closeDialog(): void { open.value = false; }
function onDialogClose(): void { open.value = false; }

function addFiles(event: Event): void {
  const input = event.target as HTMLInputElement;
  const files = Array.from(input.files ?? []);
  error.value = '';
  if (attachments.value.length + files.length > 3) {
    error.value = '最多上传 3 张图片。';
    input.value = '';
    return;
  }
  for (const file of files) {
    if (!allowedTypes.has(file.type)) { error.value = '反馈图片仅支持 JPG、PNG 或 WebP。'; break; }
    if (file.size > maxImageBytes) { error.value = '每张反馈图片不能超过 3MB。'; break; }
    attachments.value.push({ file, url: URL.createObjectURL(file) });
  }
  input.value = '';
}
function removeFile(index: number): void {
  const item = attachments.value.splice(index, 1)[0];
  if (item) URL.revokeObjectURL(item.url);
}
async function submit(): Promise<void> {
  const text = message.value.trim();
  if (!text) { error.value = '请填写反馈内容。'; return; }
  if (text.length > 2000) { error.value = '反馈内容不能超过 2000 个字符。'; return; }
  submitting.value = true;
  error.value = '';
  try {
    const result = await api.submitFeedback({
      message: text,
      contactQq: contactQq.value.trim(),
      source: props.source,
      clientUrl: window.location.href.slice(0, 2048),
      context: props.context,
      images: attachments.value.map((item) => item.file),
    });
    submitted.value = true;
    notice.value = result.emailStatus === 'failed'
      ? '反馈已保存，邮件提醒稍后重试。'
      : '反馈已收到，谢谢你！';
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '反馈提交失败，请稍后重试。';
  } finally { submitting.value = false; }
}

watch(open, async (value) => {
  if (value) { await nextTick(); dialog.value?.showModal(); }
  else if (dialog.value?.open) dialog.value.close();
});
onBeforeUnmount(releaseUrls);
</script>

<template>
  <button class="feedback-trigger" type="button" aria-label="提交反馈" @click="openDialog">反馈</button>
  <dialog ref="dialog" class="feedback-dialog" aria-labelledby="feedback-title" @close="onDialogClose" @cancel.prevent="closeDialog">
    <form class="feedback-form" @submit.prevent="submit">
      <div class="feedback-heading"><div><h2 id="feedback-title">反馈</h2><p>告诉我哪里可以做得更好。</p></div><button class="dialog-close" type="button" aria-label="关闭反馈" @click="closeDialog">×</button></div>
      <div v-if="submitted" class="feedback-success" role="status"><strong>{{ notice }}</strong><button type="button" @click="closeDialog">关闭</button></div>
      <template v-else>
        <label class="feedback-field"><span>反馈内容</span><textarea v-model="message" maxlength="2000" rows="6" autofocus placeholder="可以描述遇到的问题、建议，或附上截图说明。" /></label>
        <label class="feedback-field"><span>联系 QQ 号（可选）</span><input v-model="contactQq" inputmode="numeric" maxlength="20" placeholder="方便需要时联系你" /></label>
        <div class="feedback-field"><span>图片（可选，最多 3 张，每张不超过 3MB）</span><input id="feedback-file-input" ref="fileInput" class="feedback-file-input sr-only" type="file" accept="image/jpeg,image/png,image/webp" multiple @change="addFiles" /><div class="feedback-file-picker"><label class="feedback-file-button" for="feedback-file-input">选择文件</label><span class="feedback-file-name">{{ attachments.length ? attachments.map((item) => item.file.name).join('、') : '尚未选择图片' }}</span></div><div v-if="attachments.length" class="feedback-previews"><figure v-for="(item, index) in attachments" :key="item.url"><img :src="item.url" alt="反馈图片预览" /><button type="button" :aria-label="`删除第 ${index + 1} 张图片`" @click="removeFile(index)">×</button></figure></div></div>
        <p v-if="error" class="feedback-error" role="alert">{{ error }}</p>
        <div class="feedback-actions"><button type="button" class="feedback-cancel" @click="closeDialog">取消</button><button type="submit" class="feedback-submit" :disabled="submitting">{{ submitting ? '正在发送…' : '提交反馈' }}</button></div>
      </template>
    </form>
  </dialog>
</template>

<style scoped>
.feedback-trigger { min-height: 40px; border: 0; border-radius: var(--radius-button); padding: 0 14px; color: var(--color-text-muted); background: transparent; font: inherit; font-weight: 650; cursor: pointer; }
.feedback-trigger:hover { color: var(--color-action); background: var(--color-surface-accent); }
@media (max-width: 600px) { .feedback-trigger { min-height: 32px; padding: 0 8px; font-size: 14px; } }
.feedback-dialog { width: min(620px, calc(100vw - 32px)); max-height: min(720px, calc(100vh - 32px)); padding: 0; border: 1px solid var(--color-border); border-radius: 20px; color: var(--color-text); background: var(--color-surface); box-shadow: 0 24px 70px rgba(51, 39, 24, .24); }
.feedback-dialog::backdrop { background: rgba(51, 39, 24, .32); }
.feedback-form { padding: 24px; overflow-y: auto; }
.feedback-heading { display: flex; justify-content: space-between; gap: 20px; align-items: flex-start; margin-bottom: 20px; }.feedback-heading h2 { margin: 0; font-size: 22px; }.feedback-heading p { margin: 6px 0 0; color: var(--color-text-muted); font-size: 13px; }.dialog-close { width: 32px; height: 32px; border: 0; border-radius: 50%; color: var(--color-text-muted); background: transparent; font-size: 24px; cursor: pointer; }.dialog-close:hover { color: var(--color-action); background: var(--color-surface-accent); }
.feedback-field { display: grid; gap: 7px; margin-top: 14px; color: var(--color-text-muted); font-size: 13px; font-weight: 700; }.feedback-field input, .feedback-field textarea { width: 100%; box-sizing: border-box; border: 1px solid var(--color-border); border-radius: 10px; padding: 10px 12px; color: var(--color-text); background: var(--color-surface-warm); font: inherit; font-weight: 400; }.feedback-field textarea { resize: vertical; line-height: 1.6; }
.feedback-file-picker { display: flex; min-width: 0; align-items: center; gap: 10px; min-height: 42px; border: 1px solid var(--color-border); border-radius: 10px; padding: 4px 10px 4px 4px; background: var(--color-surface-warm); }.feedback-file-button { display: inline-flex; min-height: 34px; align-items: center; flex: 0 0 auto; border: 1px solid var(--color-border); border-radius: var(--radius-button); padding: 0 12px; color: var(--color-text); background: var(--color-surface); font: inherit; font-size: 13px; font-weight: 650; cursor: pointer; }.feedback-file-button:hover { border-color: var(--color-action); color: var(--color-action); background: var(--color-surface-accent); }.feedback-file-name { min-width: 0; overflow: hidden; color: var(--color-text-muted); font-size: 12px; font-weight: 400; text-overflow: ellipsis; white-space: nowrap; }
.feedback-file-input { width: 1px !important; height: 1px !important; padding: 0 !important; border: 0 !important; }
.feedback-previews { display: flex; flex-wrap: wrap; gap: 10px; }.feedback-previews figure { position: relative; width: 88px; height: 68px; margin: 0; }.feedback-previews img { width: 100%; height: 100%; border-radius: 8px; object-fit: cover; }.feedback-previews button { position: absolute; top: -7px; right: -7px; width: 22px; height: 22px; border: 1px solid var(--color-border); border-radius: 50%; color: var(--color-text); background: #fff; cursor: pointer; }
.feedback-error { margin: 14px 0 0; color: var(--color-danger); font-size: 13px; }.feedback-success { display: grid; gap: 18px; margin-top: 8px; padding: 22px; border: 1px solid var(--color-border); border-radius: 16px; color: var(--color-text); background: var(--color-surface-warm); }.feedback-success strong { font-size: 16px; line-height: 1.6; }.feedback-success button { justify-self: start; min-height: 40px; border: 0; border-radius: 9px; padding: 0 15px; color: #fff; background: var(--color-action); font: inherit; font-weight: 650; cursor: pointer; }.feedback-success button:hover { background: var(--color-action-hover); }.feedback-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 22px; }.feedback-cancel, .feedback-submit { min-height: 40px; border: 0; border-radius: 9px; padding: 0 15px; font: inherit; cursor: pointer; }.feedback-cancel { color: var(--color-text-muted); background: transparent; }.feedback-submit { color: #fff; background: var(--color-action); }.feedback-submit:disabled { opacity: .6; cursor: default; }
@media (max-width: 600px) { .feedback-form { padding: 20px; } }
</style>
