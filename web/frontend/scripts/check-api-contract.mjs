import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const client = await readFile(new URL('../src/api/client.ts', import.meta.url), 'utf8');
const attemptComposable = await readFile(new URL('../src/composables/useAttempt.ts', import.meta.url), 'utf8');
const quizPage = await readFile(new URL('../src/pages/QuizPage.vue', import.meta.url), 'utf8');
const answerOption = await readFile(new URL('../src/components/AnswerOption.vue', import.meta.url), 'utf8');
const baseStyles = await readFile(new URL('../src/styles/base.css', import.meta.url), 'utf8');

assert.match(client, /X-Quiz-Attempt/, '匿名答题必须使用 X-Quiz-Attempt 请求头');
assert.match(client, /attempt_token/, '创建答题必须读取后端返回的 attempt_token');
assert.match(client, /image_url/, '题目写入必须映射为后端的 image_url');
assert.match(client, /font_presets/, '设置读写必须映射为后端的 font_presets');
assert.match(client, /body\?\.error\?\.message/, '错误提示必须读取稳定 error envelope');
assert.doesNotMatch(client, /hanzipen-admin-token/, 'Web 管理员会话不得写入 localStorage');
assert.match(client, /const headers = new Headers\(init\.headers\)/, '请求头必须从调用方 headers 开始合并');
assert.match(client, /if \(init\.body && !headers\.has\('Content-Type'\)\)/, 'JSON 请求必须自动补齐 Content-Type');
assert.match(client, /init\.body instanceof FormData/, '图片上传必须保留浏览器生成的 multipart boundary');
assert.match(client, /uploadImage: async \(file: File\)/, '管理端必须通过文件上传接口而非暴露 WebDAV 凭据');
assert.match(client, /\.\.\.init,\s*credentials: 'same-origin',\s*headers,/, '合并后的 headers 必须在 init 展开后传给 fetch');
assert.match(attemptComposable, /attempt\.value = \{ \.\.\.attempt\.value, submitted: true \}/, '提交成功后必须封存内存答题会话');
assert.doesNotMatch(quizPage, /onBeforeRouteLeave/, '退出答题不应出现二次确认');
assert.match(quizPage, /function restart[\s\S]*clearSavedAttempt\(\)/, '重新开始必须清除当前答题进度');
assert.match(answerOption, /@keydown="handleKeydown\(\$event, answer, disabled\)"/, '答题 radio 必须捕获方向键');
assert.match(quizPage, /function moveAnswer[\s\S]*event\.preventDefault\(\)/, '答题页必须接管 radio 方向键并阻止默认行为');
assert.match(quizPage, /@move="moveAnswer"/, '答题页必须消费 radio 方向事件');
assert.match(quizPage, /void nextTick\([\s\S]*input\[type="radio"\]\[name="\$\{name\}"\]\[value="\$\{nextAnswer\}"\][\s\S]*\.focus\(\)/, '方向键选择后必须把焦点移动到目标 radio');
assert.match(baseStyles, /@media \(prefers-reduced-motion: reduce\)[\s\S]*transition: none !important/, '减少动态效果时必须禁用 CSS 过渡');

console.log('API contract self-check passed.');
