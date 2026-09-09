// Run against an isolated FastAPI + Vite instance with the real sample files.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { mkdir, readdir, readFile } from 'node:fs/promises';
import path from 'node:path';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const base = process.env.BATCH_REAL_URL || 'http://127.0.0.1:5178';
const sampleDir = process.env.BATCH_REAL_SAMPLE || path.resolve(process.cwd(), '../../sample');
const output = process.env.BATCH_REAL_OUTPUT || '/tmp/mikanquiz-real-acceptance';
const uploadDir = process.env.BATCH_REAL_UPLOADS;
const username = process.env.BATCH_REAL_USERNAME || 'operator';
const password = process.env.BATCH_REAL_PASSWORD || 'correct-password';

function clamp(value, low, high) { return Math.max(low, Math.min(high, value)); }
function overlaps(a, b) {
  return a.x < b.x + b.width && a.x + a.width > b.x && a.y < b.y + b.height && a.y + a.height > b.y;
}

async function parseAnnotations() {
  const text = await readFile(path.join(sampleDir, '笑容职场51 已校.txt'), 'utf8');
  const pages = new Map();
  for (const block of text.split(/(?=>>>>>>>>\[)/).filter((item) => item.startsWith('>>>>>>>>['))) {
    const pageMatch = block.match(/^>>>>>>>>\[(\d+\.jpeg)\]<<<<<<<</);
    if (!pageMatch) continue;
    const regions = [];
    for (const chunk of block.slice(pageMatch[0].length).split(/(?=----------------\[\d+\]----------------\[)/).filter((item) => item.startsWith('----------------['))) {
      const lines = chunk.split(/\r?\n/);
      const header = lines.shift().match(/^----------------\[(\d+)\]----------------\[([0-9.]+),([0-9.]+),([1-3])\]$/);
      if (!header) continue;
      regions.push({
        index: Number(header[1]),
        x: Number(header[2]),
        y: Number(header[3]),
        difficulty: Number(header[4]),
        text: lines.join('\n').trim(),
      });
    }
    pages.set(pageMatch[1], regions);
  }
  return pages;
}

function chooseRect(annotation, width, height, used) {
  const sizes = [[120, 90], [100, 76], [80, 60], [60, 48]];
  const centerX = annotation.x * width;
  const centerY = annotation.y * height;
  for (const [rectWidth, rectHeight] of sizes) {
    for (let radius = 0; radius <= 360; radius += 20) {
      for (let dx = -radius; dx <= radius; dx += 20) {
        for (let dy = -radius; dy <= radius; dy += 20) {
          if (radius && Math.max(Math.abs(dx), Math.abs(dy)) !== radius) continue;
          const candidate = {
            x: Math.round(clamp(centerX - rectWidth / 2 + dx, 0, width - rectWidth)),
            y: Math.round(clamp(centerY - rectHeight / 2 + dy, 0, height - rectHeight)),
            width: rectWidth,
            height: rectHeight,
          };
          if (!used.some((item) => overlaps(item, candidate))) return candidate;
        }
      }
    }
  }
  return {
    x: Math.round(clamp(centerX - 30, 0, width - 60)),
    y: Math.round(clamp(centerY - 24, 0, height - 48)),
    width: 60,
    height: 48,
  };
}

async function waitForSaved(page) {
  await page.getByText('已保存到本机', { exact: true }).waitFor({ timeout: 15000 });
}

async function drawRect(page, rect, pageWidth, pageHeight) {
  const viewport = page.locator('.canvas-viewport');
  const svg = page.locator('.canvas-viewport svg');
  const initial = await svg.boundingBox();
  assert.ok(initial, 'canvas must be visible before drawing');
  const scale = initial.width / pageWidth;
  const scroll = await viewport.evaluate((element) => ({
    clientHeight: element.clientHeight,
    scrollHeight: element.scrollHeight,
  }));
  const top = clamp((rect.y + rect.height / 2) * scale - scroll.clientHeight / 2, 0, Math.max(0, scroll.scrollHeight - scroll.clientHeight));
  await viewport.evaluate((element, value) => { element.scrollTop = value; }, top);
  await page.waitForTimeout(20);
  const bounds = await svg.boundingBox();
  assert.ok(bounds, 'canvas must remain visible after scrolling');
  const actualScale = bounds.width / pageWidth;
  await page.mouse.move(bounds.x + rect.x * actualScale, bounds.y + rect.y * actualScale);
  await page.mouse.down();
  await page.mouse.move(
    bounds.x + (rect.x + rect.width) * actualScale,
    bounds.y + (rect.y + rect.height) * actualScale,
    { steps: 3 },
  );
  await page.mouse.up();
}

async function completeRegion(page, annotation) {
  const difficulty = page.locator('.editor-scroll select').first();
  await difficulty.selectOption(String(annotation.difficulty));
  await page.getByRole('radio', { name: '真实验收字体', exact: true }).check();
  await page.getByPlaceholder('写下判别依据或补充说明').fill(
    ('样本标注：' + (annotation.text || '未提供文字')).slice(0, 1000),
  );
  await page.getByRole('button', { name: '完成并继续', exact: true }).click();
  await page.getByText('在漫画上框出', { exact: false }).waitFor({ timeout: 15000 });
  await waitForSaved(page);
}

async function main() {
  await mkdir(output, { recursive: true });
  assert.ok(uploadDir, 'BATCH_REAL_UPLOADS must point to the isolated local upload directory');
  const sampleNames = (await readdir(sampleDir))
    .filter((name) => /^\d+\.jpeg$/.test(name))
    .sort((a, b) => a.localeCompare(b, 'en', { numeric: true }));
  const annotations = await parseAnnotations();
  assert.equal(sampleNames.length, 16, 'real sample should contain 16 JPEG pages');
  assert.equal(annotations.size, 16, 'annotation file should list all 16 pages');
  const annotatedCount = [...annotations.values()].reduce((total, items) => total + items.length, 0);
  assert.equal(annotatedCount, 189, 'annotation file should contain 189 regions');

  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.BATCH_BROWSER_EXECUTABLE,
  });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  const pageErrors = [];
  const requestFailures = [];
  page.on('pageerror', (error) => pageErrors.push(error.message));
  page.on('requestfailed', (request) => requestFailures.push(request.url() + ': ' + request.failure()?.errorText));

  try {
    await page.goto(base + '/admin/login?next=%2Fadmin%2Fquestions%2Fbatch');
    await page.getByLabel('账号').fill(username);
    await page.getByLabel('密码').fill(password);
    await page.getByRole('button', { name: '登录管理端', exact: true }).click();
    await page.waitForURL('**/admin/questions/batch');
    await page.getByRole('button', { name: '＋ 新建批次' }).click();
    await page.locator('.el-message-box input').fill('真实漫画验收');
    await page.getByRole('button', { name: '创建', exact: true }).click();
    await page.getByRole('button', { name: '选择图片', exact: true }).waitFor();

    await page.locator('input[type=file]').setInputFiles(
      sampleNames.map((name) => path.join(sampleDir, name)),
    );
    await page.locator('.page-item').nth(15).waitFor({ timeout: 60000 });
    await page.locator('.canvas-viewport svg').waitFor({ timeout: 30000 });
    await waitForSaved(page);
    const pageNames = await page.locator('.page-item strong').allTextContents();
    assert.deepEqual(
      pageNames.map((name) => name.replace(/^\d+\s*·\s*/, '').trim()),
      sampleNames,
      'pages should use natural filename order',
    );

    const regionsByPage = [];
    for (let pageIndex = 0; pageIndex < sampleNames.length; pageIndex++) {
      const fileName = sampleNames[pageIndex];
      if (pageIndex > 0) {
        await page.locator('.page-item').nth(pageIndex).click();
        await page.waitForFunction((name) => document.querySelector('.toolbar-page-name')?.textContent === name, fileName);
        await page.locator('.canvas-viewport svg').waitFor();
      }
      const pageAnnotations = annotations.get(fileName) || [];
      const used = [];
      for (const annotation of pageAnnotations) {
        const rect = chooseRect(annotation, 1125, 1600, used);
        used.push(rect);
        await drawRect(page, rect, 1125, 1600);
        await completeRegion(page, annotation);
      }
      await page.getByLabel('此页已检查').check();
      await waitForSaved(page);
      regionsByPage.push({ name: fileName, regions: pageAnnotations.length });
    }

    const draft = await page.evaluate(async (owner) => {
      const module = await import('/src/lib/batchDrafts.ts');
      return (await module.listDrafts(owner))[0];
    }, username);
    assert.equal(draft.pages.length, 16);
    assert.equal(draft.pages.reduce((total, item) => total + item.regions.length, 0), 189);
    assert.ok(draft.pages.every((item) => item.checked), 'every real page should be marked checked');
    assert.ok(draft.pages.every((item) => item.regions.every((item) => item.status === 'ready')), 'every annotation should be ready');
    await page.screenshot({ path: path.join(output, 'real-workspace-1440.png'), fullPage: true });

    await page.getByRole('button', { name: '检查并入库 · 189', exact: true }).click();
    await page.getByRole('heading', { name: '检查并入库', exact: true }).waitFor();
    await page.getByRole('button', { name: '入库／重试 189 题', exact: true }).click();
    await page.getByText('本次提交结束，请查看逐题结果', { exact: true }).waitFor({ timeout: 300000 });
    await page.getByText('已入库 189 题', { exact: false }).waitFor({ timeout: 15000 });

    const apiResult = await page.evaluate(async () => {
      const pages = await Promise.all([1, 2].map(async (pageNumber) => {
        const response = await fetch('/api/v1/admin/questions?page=' + pageNumber + '&page_size=100&sort_by=id&sort_order=asc');
        return response.json();
      }));
      return {
        total: pages[0].total,
        items: pages.flatMap((item) => item.items),
      };
    });
    assert.equal(apiResult.total, 189);
    assert.equal(apiResult.items.length, 189);
    assert.ok(apiResult.items.every((item) => item.image_url?.startsWith('http://127.0.0.1:8001/uploads/')));
    assert.ok(apiResult.items.every((item) => item.correct_option_id === 1));
    const firstImageUrl = apiResult.items[0].image_url;
    const imageResponse = await fetch(firstImageUrl);
    assert.equal(imageResponse.status, 200);
    assert.ok((await imageResponse.arrayBuffer()).byteLength > 100);

    const uploadNames = await readdir(uploadDir);
    assert.equal(uploadNames.length, 189, 'local storage should contain one crop per question');
    assert.deepEqual(pageErrors, []);
    assert.deepEqual(requestFailures, []);
    await page.screenshot({ path: path.join(output, 'real-review-1440.png'), fullPage: true });
    console.log(JSON.stringify({
      pass: true,
      samplePages: sampleNames.length,
      annotatedPages: [...annotations.values()].filter((items) => items.length > 0).length,
      annotatedRegions: annotatedCount,
      createdQuestions: apiResult.total,
      uploadedFiles: uploadNames.length,
      output,
      regionsByPage,
    }, null, 2));
  } catch (error) {
    try {
      await page.screenshot({ path: path.join(output, 'real-failure.png'), fullPage: true });
      console.error(await page.locator('body').innerText());
    } catch { /* preserve the original failure */ }
    throw error;
  } finally {
    await browser.close();
  }
}

await main();
