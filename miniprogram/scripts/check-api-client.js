const assert = require("assert");
const fs = require("fs");
const path = require("path");
const api = require("../services/api");

const { normalizeAttempt, normalizePublicQuestion, normalizeSubmission } = api.__internal;

function walk(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const item = path.join(directory, entry.name);
    return entry.isDirectory() ? walk(item) : [item];
  });
}

function testPublicQuestionDoesNotContainAnswer() {
  const attempt = normalizeAttempt({
    attempt_token: "token", mode: "beginner", expires_at: "2030-01-01T00:00:00Z",
    questions: [{
      id: "q-1", text: "题目", image_url: "https://images.example/q.jpg", difficulty: 2,
      options: ["A", "B", "C", "D"], answer: "B", explanation: "不应出现",
    }],
  });
  assert.strictEqual(attempt.attemptToken, "token");
  assert.deepStrictEqual(attempt.attempt.questions[0], {
    id: "q-1", text: "题目", imageUrl: "https://images.example/q.jpg", difficulty: 2,
    options: ["A", "B", "C", "D"],
  });
  assert.strictEqual("answer" in attempt.attempt.questions[0], false);
}

function testSubmissionRetainsReviewDataOnlyAfterSubmit() {
  const result = normalizeSubmission({ details: [{
    question_id: "q-1", question_text: "题目", correct_answer: "B",
    selected: "A", explanation: "解析", is_correct: false,
  }] });
  assert.strictEqual(result.details[0].id, "q-1");
  assert.strictEqual(result.details[0].answer, "B");
  assert.strictEqual(result.details[0].explanation, "解析");
}

function testLegacyCloudCallsAreAbsent() {
  const root = path.resolve(__dirname, "..");
  const sources = [path.join(root, "app.js"), ...walk(path.join(root, "pages"))]
    .filter((file) => /\.(js|wxml|wxss)$/.test(file));
  const banned = /wx\.cloud\.(?:callFunction|uploadFile|init)|imageFileID/;
  sources.forEach((file) => {
    assert.strictEqual(banned.test(fs.readFileSync(file, "utf8")), false, `legacy cloud reference: ${file}`);
  });
}

function testResultMarkupRendersWrongDetails() {
  const markup = fs.readFileSync(
    path.resolve(__dirname, "../pages/quiz/quiz.wxml"), "utf8"
  );
  ["result.wrongDetails", "你的答案", "正确答案", "解析", "previewReviewImage"].forEach((text) => {
    assert.strictEqual(markup.includes(text), true, `missing result review markup: ${text}`);
  });
}

async function testTransportHeadersAndPayloads() {
  const calls = [];
  global.wx = {
    request(options) {
      calls.push(options);
      options.success({ statusCode: 200, data: { details: [] } });
    },
  };
  await api.submitAttempt("attempt-token", { 1: "A" }, "昵称");
  await api.createAdminQuestion("admin-token", {
    text: "题目", imageUrl: "https://images.example/q.jpg", difficulty: 1,
    options: ["A", "B", "C", "D"], answer: "A", explanation: "解析",
  });
  assert.strictEqual(calls[0].header["X-Quiz-Attempt"], "attempt-token");
  assert.strictEqual(calls[0].header.Authorization, undefined);
  assert.strictEqual(calls[0].data.display_name, "昵称");
  assert.strictEqual(calls[1].header.Authorization, "Bearer admin-token");
  assert.strictEqual(calls[1].data.image_url, "https://images.example/q.jpg");
  delete global.wx;
}

async function run() {
  testPublicQuestionDoesNotContainAnswer();
  testSubmissionRetainsReviewDataOnlyAfterSubmit();
  testLegacyCloudCallsAreAbsent();
  testResultMarkupRendersWrongDetails();
  await testTransportHeadersAndPayloads();
  console.log("miniprogram API adapter checks passed");
}

run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
