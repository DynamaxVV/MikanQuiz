const cloud = require("wx-server-sdk");
const crypto = require("crypto");
const { DEFAULT_SETTINGS, gradeQuestions, sanitizeQuestion, selectQuestions, validateQuestion, validateSettings } = require("./lib/quiz");

cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV });
const db = cloud.database();
const questions = db.collection("quiz_questions");
const submissions = db.collection("quiz_submissions");
const settingsCollection = db.collection("quiz_settings");
const adminSessions = db.collection("quiz_admin_sessions");

function isAdmin(openid) {
  return (process.env.ADMIN_OPENIDS || "").split(",").map((item) => item.trim()).includes(openid);
}

function validPassword(value, expected) {
  const input = Buffer.from(value || "");
  const target = Buffer.from(expected || "");
  return input.length === target.length && crypto.timingSafeEqual(input, target);
}

async function createAdminSession(openid) {
  const token = crypto.randomBytes(32).toString("hex");
  await adminSessions.add({ data: { token, openid, expiresAt: new Date(Date.now() + 8 * 60 * 60 * 1000) } });
  return token;
}

async function assertAdmin(openid, token) {
  if (isAdmin(openid)) return;
  if (!token) throw new Error("请先登录管理员账号");
  const response = await adminSessions.where({ token, openid }).limit(1).get();
  if (!response.data[0] || new Date(response.data[0].expiresAt).getTime() <= Date.now()) throw new Error("管理员登录已失效");
}

async function allQuestions() {
  return (await questions.orderBy("createdAt", "desc").limit(100).get()).data;
}

async function getSettings() {
  try {
    const saved = (await settingsCollection.doc("default").get()).data;
    return { ...DEFAULT_SETTINGS, ...saved, modes: { ...DEFAULT_SETTINGS.modes, ...(saved.modes || {}) } };
  }
  catch (error) { return DEFAULT_SETTINGS; }
}

exports.main = async (event) => {
  const { OPENID } = cloud.getWXContext();
  if (!OPENID) throw new Error("未能取得微信登录身份");
  if (event.action === "me") return { isAdmin: isAdmin(OPENID) };
  if (event.action === "adminLogin") {
    const passwordLogin = process.env.ADMIN_USERNAME && process.env.ADMIN_PASSWORD && event.username === process.env.ADMIN_USERNAME && validPassword(event.password, process.env.ADMIN_PASSWORD);
    if (event.method === "wechat" && !isAdmin(OPENID)) throw new Error("当前微信身份不是管理员");
    if (event.method === "password" && !passwordLogin) throw new Error("账号或密码错误");
    if (event.method !== "wechat" && event.method !== "password") throw new Error("不支持的登录方式");
    return { token: await createAdminSession(OPENID) };
  }
  if (event.action === "getQuizSettings") return { settings: await getSettings() };
  if (event.action === "getQuestions") {
    const settings = await getSettings();
    return { questions: selectQuestions(await allQuestions(), settings, event.mode).map(sanitizeQuestion) };
  }
  if (event.action === "submit") {
    const result = gradeQuestions(await allQuestions(), event.answers || {});
    const displayName = typeof event.displayName === "string" ? event.displayName.trim().slice(0, 20) : "";
    await submissions.add({ data: { openid: OPENID, displayName, score: result.score, correctCount: result.correctCount, total: result.total, answers: result.details.map((item) => ({ questionId: item._id, selected: item.selected, isCorrect: item.isCorrect })), submittedAt: db.serverDate() } });
    return result;
  }
  await assertAdmin(OPENID, event.adminToken);
  if (event.action === "adminStatus") return { authorized: true };
  if (event.action === "listAdminQuestions") return { questions: await allQuestions() };
  if (event.action === "getAdminSettings") return { settings: await getSettings() };
  if (event.action === "saveQuizSettings") {
    const message = validateSettings(event.settings);
    if (message) throw new Error(message);
    await settingsCollection.doc("default").set({ data: event.settings });
    return { ok: true };
  }
  if (event.action === "saveQuizStrategy") {
    const current = await getSettings();
    const settings = { questionCount: event.settings && event.settings.questionCount, modes: event.settings && event.settings.modes, fontPresets: current.fontPresets || [] };
    const message = validateSettings(settings);
    if (message) throw new Error(message);
    await settingsCollection.doc("default").set({ data: settings });
    return { ok: true };
  }
  if (event.action === "saveFontPresets") {
    const fontPresets = Array.isArray(event.fontPresets) ? event.fontPresets.map((item) => String(item).trim()).filter(Boolean).slice(0, 100) : null;
    if (!fontPresets || fontPresets.some((item) => item.length > 50)) throw new Error("字体快捷项格式不正确");
    const current = await getSettings();
    await settingsCollection.doc("default").set({ data: { questionCount: current.questionCount, modes: current.modes, fontPresets } });
    return { ok: true };
  }
  if (event.action === "listSubmissions") return { submissions: (await submissions.orderBy("submittedAt", "desc").limit(100).get()).data.map((item) => ({ ...item, userLabel: item.displayName || `微信用户 · ${(item.openid || "未知").slice(-6)}` })) };
  if (event.action === "saveQuestion") {
    const message = validateQuestion(event.question);
    if (message) throw new Error(message);
    const item = event.question;
    await questions.add({ data: { text: item.text.trim(), imageFileID: item.imageFileID || "", difficulty: item.difficulty, options: item.options.map((option) => option.trim()), answer: item.answer, explanation: (item.explanation || (item.explanations || {})[item.answer] || "").trim(), createdAt: db.serverDate() } });
    return { ok: true };
  }
  if (event.action === "updateQuestion") {
    if (!event.id) throw new Error("缺少题目 ID");
    const message = validateQuestion(event.question);
    if (message) throw new Error(message);
    const item = event.question;
    await questions.doc(event.id).update({ data: { text: item.text.trim(), imageFileID: item.imageFileID || "", difficulty: item.difficulty, options: item.options.map((option) => option.trim()), answer: item.answer, explanation: (item.explanation || (item.explanations || {})[item.answer] || "").trim(), updatedAt: db.serverDate() } });
    return { ok: true };
  }
  if (event.action === "deleteQuestion") {
    if (!event.id) throw new Error("缺少题目 ID");
    await questions.doc(event.id).remove();
    return { ok: true };
  }
  throw new Error("未知操作");
};
