// Run with a local Vite server. APIs are intercepted; no real server or images are used.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { mkdir } from 'node:fs/promises';
const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const base = process.env.BATCH_TEST_URL || 'http://127.0.0.1:5178';
const output = process.env.BATCH_TEST_OUTPUT || '/tmp/mikanquiz-batch-check';
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true, executablePath: process.env.BATCH_BROWSER_EXECUTABLE });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await context.newPage();
const errors = [];
page.on('pageerror', error => errors.push(error.message));
const receipts = new Map();
const explanationCaches = new Map();
let uploads = 0;
let loseResponse = true;
let failUpload = false;
let expire = false;
const group = { id: 1, name: '类黑', sort_order: 0, options: [
  { id: 1, name: '合成黑体', minimum_difficulty: 1, sort_order: 0, font_url: null },
  { id: 2, name: '合成高难字体', minimum_difficulty: 3, sort_order: 1, font_url: null },
] };
await context.route('**/api/v1/**', async route => {
  const path = new URL(route.request().url()).pathname;
  const json = (body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
  const cacheMatch = path.match(/\/admin\/font-explanation-cache\/(\d+)$/);
  if (cacheMatch) {
    const fontOptionId = Number(cacheMatch[1]);
    if (route.request().method() === 'PUT') {
      const { explanation } = route.request().postDataJSON();
      explanationCaches.set(fontOptionId, explanation);
    }
    return json({ font_option_id: fontOptionId, explanation: explanationCaches.get(fontOptionId) || '', updated_at: explanationCaches.has(fontOptionId) ? '2099-01-01T00:00:00Z' : null });
  }
  if (path.endsWith('/admin/session')) return json({ username: 'synthetic-operator', expires_at: '2099-01-01T00:00:00Z' });
  if (path.endsWith('/admin/option-groups')) return json([group]);
  if (path.endsWith('/admin/images')) {
    if (failUpload) { failUpload = false; return route.abort(); }
    uploads++; return json({ image_url: `https://example.test/crop-${uploads}.png` }, 201);
  }
  if (path.endsWith('/admin/questions') && route.request().method() === 'POST') {
    if (expire) { expire = false; return json({ error: { code: 'ADMIN_AUTH_REQUIRED', message: '登录已过期' } }, 401); }
    const payload = route.request().postDataJSON();
    const key = payload.client_request_id;
    assert.ok(key);
    if (receipts.has(key)) assert.deepEqual(receipts.get(key).payload, payload);
    else receipts.set(key, { payload, id: receipts.size + 1 });
    if (loseResponse) { loseResponse = false; return route.abort(); }
    return json({ ...payload, id: receipts.get(key).id, correct_option: group.options[0], correct_group: group }, 201);
  }
  throw new Error(`Unexpected real API request: ${path}`);
});
async function stored() {
  return page.evaluate(async () => {
    const { listDrafts } = await import('/src/lib/batchDrafts.ts');
    return (await listDrafts('synthetic-operator'))[0];
  });
}
async function waitSaved() { await page.getByText('已保存到本机', { exact: true }).waitFor(); }
async function draw(x, y, w, h) {
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.locator('.canvas-viewport').evaluate(element => { element.scrollTop = 0; element.scrollLeft = 0; });
  const svg = page.locator('.canvas-viewport svg');
  const bounds = await svg.boundingBox();
  const dimensions = await svg.getAttribute('viewBox');
  const scale = bounds.width / Number(dimensions.split(' ')[2]);
  await page.mouse.move(bounds.x + x * scale, bounds.y + y * scale);
  await page.mouse.down();
  await page.mouse.move(bounds.x + (x + w) * scale, bounds.y + (y + h) * scale, { steps: 4 });
  await page.mouse.up();
}
async function resizeSelected(dx, dy) {
  const handle = page.locator('.handle[data-corner="se"]');
  await handle.scrollIntoViewIfNeeded();
  const handleBounds = await handle.boundingBox();
  const svg = page.locator('.canvas-viewport svg');
  const svgBounds = await svg.boundingBox();
  const viewBox = await svg.getAttribute('viewBox');
  assert.ok(handleBounds && svgBounds && viewBox);
  const scale = svgBounds.width / Number(viewBox.split(' ')[2]);
  const x = handleBounds.x + handleBounds.width / 2;
  const y = handleBounds.y + handleBounds.height / 2;
  await page.mouse.move(x, y);
  await page.mouse.down();
  await page.mouse.move(x + dx * scale, y + dy * scale, { steps: 4 });
  await page.mouse.up();
}
async function complete(text) {
  await page.getByRole('radio', { name: '合成黑体', exact: true }).check();
  await page.getByPlaceholder('写下判别依据或补充说明').fill(text);
  await page.getByRole('button', { name: '完成并继续', exact: true }).click();
  await page.getByText('在漫画上框出').waitFor();
  await waitSaved();
}
try {
  await page.goto(`${base}/admin/questions/batch`);
  await page.getByRole('button', { name: '＋ 新建批次' }).click();
  await page.locator('.el-message-box input').fill('合成漫画验收');
  await page.getByRole('button', { name: '创建', exact: true }).click();
  await page.getByRole('dialog').waitFor({ state: 'hidden' });
  await page.getByRole('button', { name: '选择图片', exact: true }).waitFor();
  const png = await page.evaluate(() => {
    const c = document.createElement('canvas'); c.width = 1200; c.height = 1800;
    const g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, 1200, 1800);
    for (let i = 0; i < 8; i++) {
      g.strokeStyle = '#bbb'; g.strokeRect(50, 40 + i * 210, 1100, 180);
      g.fillStyle = '#222'; g.font = '42px sans-serif'; g.fillText(`合成文字区域 ${i + 1} ABC 字体`, 85, 120 + i * 210);
    }
    return c.toDataURL('image/png').split(',')[1];
  });
  await page.locator('input[type=file]').setInputFiles([10, 2, 1, ...Array.from({ length: 7 }, (_, index) => index + 3)].map(n => ({ name: `${n}.png`, mimeType: 'image/png', buffer: Buffer.from(png, 'base64') })));
  await page.locator('.rail-heading strong').filter({ hasText: '页面 · 10' }).waitFor();
  await page.locator('.page-item').nth(2).waitFor();
  await page.locator('.canvas-viewport svg').waitFor();
  await waitSaved();
  const canvasHeight = await page.locator('.canvas-viewport').evaluate(element => element.clientHeight);
  assert.ok(canvasHeight >= 650, `Tall manga canvas should reserve vertical space (got ${canvasHeight}px)`);
  assert.equal(await page.locator('.page-actions').count(), 0, 'The left page action bar should be removed');
  for (const name of ['上移', '下移', '移除']) assert.equal(await page.getByRole('button', { name, exact: true }).count(), 0, `${name} page action should be removed`);
  assert.equal(await page.locator('.region-strip').count(), 0, 'The redundant bottom region bar should be removed');
  assert.deepEqual((await stored()).pages.map(p => p.name), ['1.png', '2.png', '3.png', '4.png', '5.png', '6.png', '7.png', '8.png', '9.png', '10.png']);
  const pageListMetrics = await page.locator('.page-list').evaluate(element => ({ clientHeight: element.clientHeight, scrollHeight: element.scrollHeight, overflowY: getComputedStyle(element).overflowY }));
  assert.equal(pageListMetrics.overflowY, 'auto');
  assert.ok(pageListMetrics.scrollHeight > pageListMetrics.clientHeight, 'Page thumbnails should scroll when they exceed the rail height');
  await draw(70, 50, 500, 130);
  await complete('第一处合成解析');
  const first = (await stored()).pages[0].regions[0];
  assert.deepEqual([first.x, first.y, first.width, first.height], [70, 50, 500, 130]);
  await page.locator('.region rect[data-region]').first().click();
  await page.locator('.canvas-viewport svg').evaluate(el => el.focus({ preventScroll: true }));
  await page.keyboard.press('ArrowRight');
  await waitSaved();
  assert.equal((await stored()).pages[0].regions[0].status, 'draft');
  assert.equal((await stored()).pages[0].regions[0].x, 71);
  await resizeSelected(20, 30); // drag southeast resize handle
  await waitSaved();
  assert.equal((await stored()).pages[0].regions[0].width, 520);
  await complete('第一处合成解析');
  // Zoom and create in source coordinates, then check native crop dimensions.
  await page.getByRole('button', { name: '缩小', exact: true }).click();
  await draw(80, 270, 450, 120);
  await page.getByRole('radio', { name: '合成黑体', exact: true }).check();
  await page.getByText('已有同字体解析', { exact: false }).waitFor();
  const explanation = page.locator('textarea').first();
  assert.equal(await explanation.getAttribute('placeholder'), '第一处合成解析');
  await explanation.press('Tab');
  assert.equal(await explanation.inputValue(), '第一处合成解析');
  await page.getByRole('button', { name: '完成并继续', exact: true }).click();
  await page.getByText('在漫画上框出').waitFor();
  await waitSaved();
  await draw(80, 490, 450, 120);
  await page.getByPlaceholder('写下判别依据或补充说明').fill('待补充的解析');
  assert.equal(await page.locator('.crop-preview').count(), 0, 'Batch editor should not render a duplicate crop screenshot');
  await page.screenshot({ path: `${output}/editor-1440.png` });
  await page.getByRole('button', { name: '暂留待补', exact: true }).click();
  await waitSaved();
  await page.screenshot({ path: `${output}/workspace-1440.png` });
  // Reload must restore originals, fields and rectangles; draft must not be published.
  await page.reload();
  await page.getByRole('button', { name: '继续上次制题', exact: true }).click();
  await page.locator('.canvas-viewport svg').waitFor();
  assert.equal((await stored()).pages[0].regions.length, 3);
  const cropSize = await page.evaluate(async () => {
    const m = await import('/src/lib/batchDrafts.ts');
    const draft = (await m.listDrafts('synthetic-operator'))[0];
    const { file } = await m.cropImage(draft.pages[0], draft.pages[0].regions[1]);
    const image = await createImageBitmap(file); const result = [image.width, image.height]; image.close(); return result;
  });
  assert.deepEqual(cropSize, [450, 120]);
  // A second tab cannot acquire the same batch.
  const second = await context.newPage();
  await second.goto(`${base}/admin/questions/batch`);
  await second.getByRole('button', { name: '继续上次制题', exact: true }).click();
  await second.getByText('此批次正在另一个标签页编辑', { exact: false }).waitFor();
  await second.close();
  await page.getByRole('button', { name: '检查并入库 · 2', exact: true }).click();
  await page.locator('.review-view').waitFor();
  assert.equal(await page.locator('.review-preview').count(), 3);
  assert.equal(await page.locator('.review-preview-options').count(), 3);
  const statusFilter = page.getByLabel('题目状态');
  assert.deepEqual(await statusFilter.locator('option').allTextContents(), ['全部 · 3', '已入库 · 0', '待入库 · 2', '待补充 · 1', '已删除 · 0']);
  await statusFilter.selectOption('pending');
  assert.equal(await page.locator('.review-preview').count(), 2);
  await statusFilter.selectOption('draft');
  assert.equal(await page.locator('.review-preview').count(), 1);
  await statusFilter.selectOption('all');
  assert.equal(await page.locator('.review-preview').count(), 3);
  assert.equal(await page.locator('.review-preview h3').first().textContent(), '请选择以下日文对应的汉字字体');
  assert.equal(await page.locator('.review-preview .preview-option').filter({ hasText: '正确' }).count(), 0, 'Selected review options should not add a redundant label');
  failUpload = true;
  await page.getByRole('button', { name: '入库／重试 2 题', exact: true }).click();
  await page.getByText('本次提交结束，请查看逐题结果', { exact: true }).waitFor();
  assert.equal(receipts.size, 1); // second item saved at server, response lost
  assert.equal(uploads, 1);
  const interrupted = await stored();
  assert.deepEqual(interrupted.pages[0].regions.map(r => r.status), ['ready', 'pending', 'draft']);
  // Reload and retry the persisted exact request, never upload the second image twice.
  await page.reload();
  await page.getByRole('button', { name: '继续上次制题', exact: true }).click();
  await page.getByRole('button', { name: '检查并入库 · 2', exact: true }).click();
  await page.getByRole('button', { name: '入库／重试 2 题', exact: true }).click();
  await page.getByText('本次提交结束，请查看逐题结果', { exact: true }).waitFor();
  assert.equal(receipts.size, 2);
  assert.equal(uploads, 2);
  assert.deepEqual((await stored()).pages[0].regions.map(r => r.status), ['saved', 'saved', 'draft']);
  await page.screenshot({ path: `${output}/review-1440.png` });
  await page.getByRole('button', { name: '← 继续框选', exact: true }).click();
  await page.locator('.region rect[data-region]').nth(2).click();
  await complete('第三处合成解析');
  await page.getByRole('button', { name: '检查并入库 · 1', exact: true }).click();
  expire = true;
  await page.getByRole('button', { name: '入库／重试 1 题', exact: true }).click();
  await page.getByText('已暂停，剩余题目已保留', { exact: true }).waitFor();
  assert.equal((await stored()).pages[0].regions[2].status, 'pending');
  await page.getByRole('button', { name: '入库／重试 1 题', exact: true }).click();
  await page.getByText('本次提交结束，请查看逐题结果', { exact: true }).waitFor();
  assert.equal(receipts.size, 3);
  assert.equal(uploads, 3);
  await page.getByRole('button', { name: '← 继续框选', exact: true }).click();
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.screenshot({ path: `${output}/workspace-1280.png` });
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  await page.setViewportSize({ width: 640, height: 400 });
  await page.screenshot({ path: `${output}/workspace-narrow.png` });
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  // Synthetic persistence stress: 36 originals / 108 regions, no network or real manga.
  const stress = await page.evaluate(async () => {
    const m = await import('/src/lib/batchDrafts.ts');
    const original = (await m.listDrafts('synthetic-operator'))[0];
    const blob = await m.readImage(original.pages[0].id);
    const batch = { ...structuredClone(original), id: crypto.randomUUID(), owner: 'synthetic-stress', name: '36 页合成存储检查', pages: [] };
    for (let i = 0; i < 36; i++) {
      const p = structuredClone(original.pages[0]); p.id = crypto.randomUUID(); p.name = `${i + 1}.png`;
      p.regions.forEach(r => { r.id = crypto.randomUUID(); }); batch.pages.push(p);
      await m.addPage(batch, p, blob);
    }
    const restored = (await m.listDrafts('synthetic-stress'))[0];
    const counts = [restored.pages.length, restored.pages.flatMap(p => p.regions).length];
    // A synchronous quota failure after deleting an image must roll back the entire transaction.
    const put = IDBObjectStore.prototype.put;
    IDBObjectStore.prototype.put = function (...args) {
      if (this.name === 'drafts') throw new DOMException('Synthetic quota failure', 'QuotaExceededError');
      return put.apply(this, args);
    };
    let failed = false;
    try { await m.removePage({ ...restored, pages: restored.pages.slice(1) }, restored.pages[0].id); }
    catch { failed = true; }
    finally { IDBObjectStore.prototype.put = put; }
    const preserved = !!await m.readImage(restored.pages[0].id);
    await m.deleteDraft(restored);
    return { counts, failed, preserved, isolated: !(await m.listDrafts('other-account')).length };
  });
  assert.deepEqual(stress, { counts: [36, 108], failed: true, preserved: true, isolated: true });
  // Show an actual save failure and retain the prior committed draft until retry succeeds.
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.evaluate(() => {
    window.originalBatchPut = IDBObjectStore.prototype.put;
    IDBObjectStore.prototype.put = function (...args) {
      if (this.name === 'drafts') throw new DOMException('Synthetic quota failure', 'QuotaExceededError');
      return window.originalBatchPut.apply(this, args);
    };
  });
  await page.getByLabel('此页已检查').check();
  await page.getByText('本机保存失败', { exact: true }).waitFor();
  assert.equal((await stored()).pages[0].checked, false);
  await page.evaluate(() => { IDBObjectStore.prototype.put = window.originalBatchPut; });
  await page.getByRole('button', { name: '重试本机保存', exact: true }).click();
  await waitSaved();
  assert.equal((await stored()).pages[0].checked, true);
  assert.deepEqual(errors, []);
  console.log('PASS: synthetic image import/sorting, zoom coordinates, crop pixels, local recovery, tab lock, partial import, upload failure, lost response retry, expired login, 1280/narrow layout, 36-page/108-region local storage, quota rollback and save recovery.');
  console.log(`Screenshots: ${output}`);
} catch (error) { await page.screenshot({ path: `${output}/failure.png` }); console.error(await page.locator('body').innerText()); throw error; } finally { await browser.close(); }
