import type { QuestionPayload } from '../types';

export interface Rect { x: number; y: number; width: number; height: number; }
export interface BatchRegion extends Rect {
  id: string;
  form: QuestionPayload;
  status: 'draft' | 'ready' | 'pending' | 'saved' | 'deleted';
  preview?: string;
  uploadUrl?: string;
  request?: { id: string; payload: QuestionPayload };
  questionId?: string;
  error?: string;
}
export interface BatchPage {
  id: string;
  name: string;
  width: number;
  height: number;
  thumbnail: string;
  checked: boolean;
  regions: BatchRegion[];
}
export interface BatchDraft {
  id: string;
  owner: string;
  name: string;
  updatedAt: number;
  defaultDifficulty: number;
  pageId: string;
  regionId: string;
  pages: BatchPage[];
  /** Reusable explanations learned inside this batch only. */
  explanationCache: Record<string, string>;
}

export type BatchReviewFilter = 'all' | 'saved' | 'pending' | 'draft' | 'deleted';

export function matchesReviewFilter(status: BatchRegion['status'], filter: BatchReviewFilter): boolean {
  if (filter === 'all') return true;
  if (filter === 'saved') return status === 'saved';
  if (filter === 'pending') return status === 'ready' || status === 'pending';
  return status === filter;
}

export function rectFromPoints(a: { x: number; y: number }, b: { x: number; y: number }, width: number, height: number): Rect {
  const x1 = Math.round(Math.max(0, Math.min(width, a.x)));
  const x2 = Math.round(Math.max(0, Math.min(width, b.x)));
  const y1 = Math.round(Math.max(0, Math.min(height, a.y)));
  const y2 = Math.round(Math.max(0, Math.min(height, b.y)));
  return { x: Math.min(x1, x2), y: Math.min(y1, y2), width: Math.abs(x2 - x1), height: Math.abs(y2 - y1) };
}

export function isFrozen(region: BatchRegion): boolean {
  return ['pending', 'saved', 'deleted'].includes(region.status);
}

export function invalidateRegion(region: BatchRegion): void {
  if (isFrozen(region)) return;
  region.status = 'draft';
  delete region.preview;
  delete region.uploadUrl;
  delete region.error;
}

export function updateDifficulty(region: BatchRegion, difficulty: number): boolean {
  if (isFrozen(region) || ![1, 2, 3].includes(difficulty) || region.form.difficulty === difficulty) return false;
  region.form.difficulty = difficulty;
  invalidateRegion(region);
  return true;
}

export function regionProblem(region: BatchRegion, options: { id: string; minimumDifficulty: number }[]): string {
  if (region.width < 1 || region.height < 1) return '请框选有效区域';
  if (!region.form.text.trim()) return '请填写题干';
  const option = options.find((item) => item.id === region.form.correctOptionId);
  if (!option) return '请选择正确字体';
  if (option.minimumDifficulty > region.form.difficulty) return '正确字体的最低难度高于本题难度';
  if (!region.form.explanation.trim()) return '请填写解析';
  return '';
}

export function normalizeDraft(draft: BatchDraft): BatchDraft {
  return { ...draft, explanationCache: { ...(draft.explanationCache ?? {}) } };
}

export function cachedExplanation(draft: BatchDraft, fontOptionId: string): string {
  return draft.explanationCache?.[fontOptionId]?.trim() ?? '';
}

export function rememberExplanation(draft: BatchDraft, fontOptionId: string, explanation: string): void {
  const value = explanation.trim();
  if (fontOptionId && value) draft.explanationCache[fontOptionId] = value;
}

let connection: Promise<IDBDatabase> | undefined;
function database(): Promise<IDBDatabase> {
  return connection ??= new Promise((resolve, reject) => {
    const request = indexedDB.open('mikanquiz-batch-drafts', 1);
    request.onupgradeneeded = () => {
      request.result.createObjectStore('drafts', { keyPath: 'id' });
      request.result.createObjectStore('images');
    };
    request.onsuccess = () => {
      request.result.onversionchange = () => { request.result.close(); connection = undefined; };
      resolve(request.result);
    };
    request.onerror = () => { connection = undefined; reject(request.error); };
    request.onblocked = () => { connection = undefined; reject(new Error('请关闭其他制题标签页后重试')); };
  });
}

async function transaction<T>(stores: string[], mode: IDBTransactionMode, run: (tx: IDBTransaction) => IDBRequest<T>): Promise<T> {
  const db = await database();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(stores, mode);
    let request: IDBRequest<T>;
    tx.oncomplete = () => resolve(request.result);
    tx.onabort = () => reject(tx.error ?? new Error('本机存储写入失败'));
    tx.onerror = () => reject(tx.error ?? request?.error);
    try { request = run(tx); }
    catch (error) { tx.abort(); reject(error); }
  });
}

export async function listDrafts(owner: string): Promise<BatchDraft[]> {
  const drafts = await transaction<BatchDraft[]>(['drafts'], 'readonly', (tx) => tx.objectStore('drafts').getAll());
  return drafts.map(normalizeDraft).filter((draft) => draft.owner === owner).sort((a, b) => b.updatedAt - a.updatedAt);
}

export function saveDraft(draft: BatchDraft): Promise<IDBValidKey> {
  return transaction(['drafts'], 'readwrite', (tx) => tx.objectStore('drafts').put(normalizeDraft(draft)));
}

export function readImage(id: string): Promise<Blob | undefined> {
  return transaction(['images'], 'readonly', (tx) => tx.objectStore('images').get(id));
}

export function addPage(draft: BatchDraft, page: BatchPage, image: Blob): Promise<IDBValidKey> {
  return transaction(['images', 'drafts'], 'readwrite', (tx) => {
    tx.objectStore('images').put(image, page.id);
    return tx.objectStore('drafts').put(draft);
  });
}

export function removePage(draft: BatchDraft, pageId: string): Promise<IDBValidKey> {
  return transaction(['images', 'drafts'], 'readwrite', (tx) => {
    tx.objectStore('images').delete(pageId);
    return tx.objectStore('drafts').put(draft);
  });
}

export function deleteDraft(draft: BatchDraft): Promise<undefined> {
  return transaction(['images', 'drafts'], 'readwrite', (tx) => {
    draft.pages.forEach((page) => tx.objectStore('images').delete(page.id));
    return tx.objectStore('drafts').delete(draft.id);
  });
}

export async function decodeImage(blob: Blob): Promise<HTMLImageElement> {
  const image = new Image();
  const url = URL.createObjectURL(blob);
  try { image.src = url; await image.decode(); return image; }
  finally { URL.revokeObjectURL(url); }
}

export function thumbnail(image: CanvasImageSource, width: number, height: number): string {
  const scale = Math.min(1, 320 / Math.max(width, height));
  const canvas = document.createElement('canvas');
  canvas.width = Math.max(1, Math.round(width * scale));
  canvas.height = Math.max(1, Math.round(height * scale));
  canvas.getContext('2d')!.drawImage(image, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL('image/png');
}

export async function cropImage(page: BatchPage, rect: Rect): Promise<{ file: File; preview: string }> {
  const blob = await readImage(page.id);
  if (!blob) throw new Error('本机原图不可用，请保留当前草稿并重新打开浏览器重试');
  const image = await decodeImage(blob);
  const canvas = document.createElement('canvas');
  canvas.width = rect.width;
  canvas.height = rect.height;
  canvas.getContext('2d')!.drawImage(image, rect.x, rect.y, rect.width, rect.height, 0, 0, rect.width, rect.height);
  const png = await new Promise<Blob>((resolve, reject) => canvas.toBlob((value) => value ? resolve(value) : reject(new Error('裁图失败，请缩小区域')), 'image/png'));
  if (png.size > 8 * 1024 * 1024) throw new Error('裁图超过 8 MB，请缩小区域后重试');
  return { file: new File([png], 'crop.png', { type: 'image/png' }), preview: thumbnail(canvas, rect.width, rect.height) };
}
