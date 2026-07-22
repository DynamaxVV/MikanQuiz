const runtimeConfig = require("../config/api");

const ADMIN_TOKEN_KEY = "quiz-admin-token";
const ATTEMPT_KEY = "quiz-active-attempt";

class ApiError extends Error {
  constructor(message, status, code) {
    super(message || "请求失败，请稍后再试");
    this.name = "ApiError";
    this.status = status || 0;
    this.code = code || "REQUEST_FAILED";
  }
}

function getBaseUrl() {
  const app = typeof getApp === "function" ? getApp() : null;
  const configured = app && app.globalData && app.globalData.apiBaseUrl;
  const baseUrl = configured || runtimeConfig.apiBaseUrl;
  if (!/^https:\/\//.test(baseUrl)) {
    throw new ApiError("API 地址必须使用 HTTPS", 0, "INVALID_API_URL");
  }
  return baseUrl.replace(/\/$/, "");
}

function unwrap(payload) {
  if (payload && payload.data && typeof payload.data === "object") return payload.data;
  return payload || {};
}

function readError(payload, statusCode) {
  const body = payload || {};
  const error = body.error || {};
  return new ApiError(
    error.message || body.message || body.detail || "请求失败，请稍后再试",
    statusCode,
    error.code || body.code || "REQUEST_FAILED"
  );
}

function clearExpiredCredential(config, statusCode) {
  if (config.token && [401, 403].includes(statusCode)) wx.removeStorageSync(ADMIN_TOKEN_KEY);
  if (config.attemptToken && [401, 404, 410].includes(statusCode)) clearStoredAttempt();
}

function request(path, options) {
  const config = options || {};
  const headers = { "content-type": "application/json" };
  if (config.token) headers.Authorization = `Bearer ${config.token}`;
  if (config.attemptToken) headers["X-Quiz-Attempt"] = config.attemptToken;
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${getBaseUrl()}${path}`,
      method: config.method || "GET",
      data: config.data,
      header: headers,
      success(response) {
        if (response.statusCode >= 200 && response.statusCode < 300) {
          resolve(unwrap(response.data));
          return;
        }
        clearExpiredCredential(config, response.statusCode);
        reject(readError(response.data, response.statusCode));
      },
      fail(error) {
        reject(new ApiError(error.errMsg || "网络连接失败", 0, "NETWORK_ERROR"));
      },
    });
  });
}

function uploadAdminImage(token, filePath) {
  return new Promise((resolve, reject) => {
    wx.uploadFile({
      url: `${getBaseUrl()}/admin/images`, filePath, name: "image",
      header: { Authorization: `Bearer ${token}` },
      success(response) {
        let payload;
        try { payload = JSON.parse(response.data || "{}"); }
        catch (error) { reject(new ApiError("图片上传响应无效", response.statusCode)); return; }
        if (response.statusCode >= 200 && response.statusCode < 300) {
          resolve(unwrap(payload).image_url || unwrap(payload).imageUrl || "");
          return;
        }
        clearExpiredCredential({ token }, response.statusCode);
        reject(readError(payload, response.statusCode));
      },
      fail(error) { reject(new ApiError(error.errMsg || "图片上传失败", 0, "NETWORK_ERROR")); },
    });
  });
}

function normalizeImageUrl(item) {
  return item.imageUrl || item.image_url || "";
}

function normalizeOptionGroups(item) {
  return (item.optionGroups || item.option_groups || []).map((group) => ({
    id: String(group.id), name: group.name, sortOrder: group.sortOrder || group.sort_order || 0,
    options: (group.options || []).map((option) => ({
      id: String(option.id), name: option.name,
      minimumDifficulty: option.minimumDifficulty || option.minimum_difficulty || 1,
    })),
  }));
}

function normalizePublicQuestion(item) {
  return {
    id: String(item.id || item._id || ""),
    text: item.text || "",
    imageUrl: normalizeImageUrl(item),
    difficulty: item.difficulty || 1,
    optionGroups: normalizeOptionGroups(item),
  };
}

function normalizeAdminQuestion(item) {
  const question = normalizePublicQuestion(item);
  question.correctOptionId = String(item.correctOptionId || item.correct_option_id || "");
  question.correctOption = item.correctOption || item.correct_option || null;
  question.correctGroup = item.correctGroup || item.correct_group || null;
  question.configurationError = item.configurationError || item.configuration_error || "";
  question.explanation = item.explanation || "";
  return question;
}

function normalizeAttempt(payload) {
  const data = unwrap(payload);
  const attempt = data.attempt || data;
  const token = data.attemptToken || data.attempt_token || attempt.attemptToken;
  return {
    attemptToken: token || "",
    attempt: {
      id: String(attempt.id || attempt.attemptId || ""),
      mode: attempt.mode || data.mode || "beginner",
      expiresAt: attempt.expiresAt || attempt.expires_at || data.expiresAt || "",
      questions: (attempt.questions || data.questions || []).map(normalizePublicQuestion),
    },
  };
}

function normalizeSubmission(payload) {
  const data = unwrap(payload);
  return {
    score: data.score || 0,
    correctCount: data.correctCount || data.correct_count || 0,
    total: data.total || 0,
    details: (data.details || []).map((item) => {
      const question = normalizeAdminQuestion(item);
      question.id = String(item.questionId || item.question_id || item.id || "");
      question.text = item.questionText || item.question_text || item.text || "";
      question.optionGroups = normalizeOptionGroups(item);
      question.selected = String(item.selectedOptionId || item.selected_option_id || item.selected || "");
      question.answer = String(item.correctOptionId || item.correct_option_id || item.correctAnswer || item.correct_answer || "");
      question.isCorrect = Boolean(item.isCorrect || item.is_correct);
      return question;
    }),
  };
}

function normalizeQuestionPage(payload) {
  const data = unwrap(payload);
  return {
    items: (data.items || data.questions || []).map(normalizeAdminQuestion),
    total: data.total || 0,
    page: data.page || 1,
    pageSize: data.pageSize || data.page_size || 0,
  };
}

function normalizeSettings(payload) {
  const data = unwrap(payload);
  const settings = data.settings || data;
  return {
    questionCount: settings.questionCount || settings.question_count || 10,
    modes: settings.modes || {},
    fontPresets: settings.fontPresets || settings.font_presets || [],
  };
}

function normalizeQuestionPayload(question) {
  return {
    text: question.text,
    image_url: question.imageUrl || null,
    difficulty: question.difficulty,
    correct_option_id: Number(question.correctOptionId),
    explanation: question.explanation,
  };
}

function isStoredAttemptValid(stored, mode) {
  return Boolean(stored && stored.token && stored.mode === mode
    && stored.expiresAt && new Date(stored.expiresAt).getTime() > Date.now());
}

function getStoredAttempt(mode) {
  const stored = wx.getStorageSync(ATTEMPT_KEY);
  if (isStoredAttemptValid(stored, mode)) return stored;
  if (stored) wx.removeStorageSync(ATTEMPT_KEY);
  return null;
}

function saveStoredAttempt(attemptToken, attempt, answers) {
  wx.setStorageSync(ATTEMPT_KEY, {
    token: attemptToken,
    mode: attempt.mode,
    expiresAt: attempt.expiresAt,
    answers: answers || {},
  });
}

function clearStoredAttempt() {
  wx.removeStorageSync(ATTEMPT_KEY);
}

async function createAttempt(mode) {
  return normalizeAttempt(await request("/quiz/attempts", { method: "POST", data: { mode } }));
}

async function getCurrentAttempt(attemptToken) {
  return normalizeAttempt(await request("/quiz/attempts/current", { attemptToken }));
}

async function getCompletedAttemptResult(attemptToken) {
  const data = await request("/quiz/attempts/current", { attemptToken });
  const result = data.result || data.submission;
  return result && Array.isArray(result.details) ? normalizeSubmission(result) : null;
}

async function submitAttempt(attemptToken, answers, displayName) {
  try {
    return normalizeSubmission(await request("/quiz/attempts/submit", {
      method: "POST", attemptToken, data: { answers, display_name: displayName },
    }));
  } catch (error) {
    if (error.code !== "NETWORK_ERROR") throw error;
    try {
      const result = await getCompletedAttemptResult(attemptToken);
      if (result) return result;
    } catch (ignoreError) { /* 保留原网络错误，用户可安全重试提交。 */ }
    return normalizeSubmission(await request("/quiz/attempts/submit", {
      method: "POST", attemptToken, data: { answers, display_name: displayName },
    }));
  }
}

async function getQuizSettings() {
  return normalizeSettings(await request("/quiz/settings"));
}

async function login(username, password) {
  const data = await request("/admin/miniprogram/login", {
    method: "POST", data: { username, password },
  });
  return { token: data.token || data.accessToken || "", expiresAt: data.expiresAt || data.expires_at || "" };
}

function getAdminSession(token) {
  return request("/admin/session", { token });
}

function logout(token) {
  return request("/admin/logout", { method: "POST", token });
}

async function listAdminQuestions(token, filters) {
  const filter = filters || {};
  const params = [];
  Object.keys(filter).forEach((key) => {
    if (filter[key] !== "" && filter[key] !== undefined) {
      const apiKey = key === "pageSize" ? "page_size" : key;
      params.push(`${apiKey}=${encodeURIComponent(filter[key])}`);
    }
  });
  const query = params.length ? `?${params.join("&")}` : "";
  return normalizeQuestionPage(await request(`/admin/questions${query}`, { token }));
}

async function getAdminQuestion(token, id) {
  return normalizeAdminQuestion(await request(`/admin/questions/${encodeURIComponent(id)}`, { token }));
}

function createAdminQuestion(token, question) {
  return request("/admin/questions", { method: "POST", token, data: normalizeQuestionPayload(question) });
}

function updateAdminQuestion(token, id, question) {
  return request(`/admin/questions/${encodeURIComponent(id)}`, {
    method: "PATCH", token, data: normalizeQuestionPayload(question),
  });
}

function deleteAdminQuestion(token, id) {
  return request(`/admin/questions/${encodeURIComponent(id)}`, { method: "DELETE", token });
}

async function getAdminSettings(token) {
  return normalizeSettings(await request("/admin/settings", { token }));
}

async function getOptionGroups(token) {
  return normalizeOptionGroups(await request("/admin/option-groups", { token }));
}

function saveOptionGroups(token, groups) {
  return request("/admin/option-groups", {
    method: "PUT", token, data: { groups: groups.map((group, groupIndex) => ({
      id: group.id ? Number(group.id) : undefined, name: group.name, sort_order: groupIndex,
      options: (group.options || []).map((option, optionIndex) => ({
        id: option.id ? Number(option.id) : undefined, name: option.name,
        minimum_difficulty: Number(option.minimumDifficulty || 1), sort_order: optionIndex,
      })),
    })) },
  });
}

function saveQuizStrategy(token, settings) {
  return request("/admin/settings/strategy", {
    method: "PUT", token, data: { question_count: settings.questionCount, modes: settings.modes },
  });
}

async function listSubmissions(token, filters) {
  const data = await listRequest("/admin/submissions", token, filters);
  return {
    items: (data.items || data.submissions || []).map((item) => ({
      id: item.id, displayName: item.displayName || item.display_name || "",
      mode: item.mode, score: item.score || 0,
      correctCount: item.correctCount || item.correct_count || 0,
      total: item.total || 0, submittedAt: item.submittedAt || item.submitted_at || "",
    })),
    total: data.total || 0, page: data.page || 1,
  };
}

function listRequest(path, token, filters) {
  const filter = filters || {};
  const query = Object.keys(filter).filter((key) => filter[key] !== "" && filter[key] !== undefined)
    .map((key) => `${key === "pageSize" ? "page_size" : key}=${encodeURIComponent(filter[key])}`).join("&");
  return request(`${path}${query ? `?${query}` : ""}`, { token });
}

module.exports = {
  ADMIN_TOKEN_KEY,
  ApiError,
  ATTEMPT_KEY,
  clearStoredAttempt,
  createAdminQuestion,
  createAttempt,
  deleteAdminQuestion,
  getAdminQuestion,
  getAdminSession,
  getAdminSettings,
  getOptionGroups,
  getCurrentAttempt,
  getQuizSettings,
  getStoredAttempt,
  listAdminQuestions,
  listSubmissions,
  login,
  logout,
  saveOptionGroups,
  saveQuizStrategy,
  saveStoredAttempt,
  submitAttempt,
  uploadAdminImage,
  updateAdminQuestion,
  __internal: { normalizeAttempt, normalizePublicQuestion, normalizeSubmission },
};
