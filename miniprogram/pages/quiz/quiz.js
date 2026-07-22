const api = require("../../services/api");

function formatQuestions(questions, includeResult, attemptQuestions) {
  return questions.map((question, index) => {
    const original = (attemptQuestions || []).find((item) => String(item._id) === String(question.id));
    const stars = [];
    const difficulty = question.difficulty || (original && original.difficulty) || 1;
    for (let star = 0; star < difficulty; star += 1) stars.push(star);
    return {
      _id: question.id || (original && original._id),
      text: question.text || (original && original.text) || "",
      imageUrl: question.imageUrl || (original && original.imageUrl) || "",
      difficulty,
      answer: includeResult ? String(question.answer || question.correctOptionId || "") : "",
      selected: question.selected || "",
      selectedExplanation: includeResult ? question.explanation || "" : "",
      isCorrect: Boolean(question.isCorrect),
      number: index + 1,
      stars,
      optionGroups: question.optionGroups || (original && original.optionGroups) || [],
    };
  });
}

Page({
  data: {
    questions: [], answers: {}, loading: true, submitting: false, result: null,
    modeTitle: "", currentIndex: 0, currentQuestion: null,
  },

  onLoad(options) {
    this.mode = options.mode || "beginner";
    this.displayName = wx.getStorageSync("quiz-display-name") || "";
    this.setData({
      modeTitle: { beginner: "新手级", proficient: "熟练级", challenge: "挑战级" }[this.mode] || "新手级",
      displayName: this.displayName,
    });
    this.loadQuestions();
  },

  setCurrent(index) {
    const list = this.data.result ? this.data.result.wrongDetails : this.data.questions;
    const question = list[index];
    if (!question) return this.setData({ currentQuestion: null });
    question.selected = String(this.data.answers[question._id] || question.selected || "");
    this.setData({ currentIndex: index, currentQuestion: question });
  },

  applyAttempt(token, attempt, answers) {
    this.attemptToken = token;
    this.attempt = attempt;
    const questions = formatQuestions(attempt.questions, false);
    this.setData({ questions, answers: answers || {}, currentIndex: 0 });
    api.saveStoredAttempt(token, attempt, answers || {});
    this.setCurrent(0);
  },

  async restoreAttempt(stored) {
    const current = await api.getCurrentAttempt(stored.token);
    this.applyAttempt(current.attemptToken || stored.token, current.attempt, stored.answers);
  },

  async createAttempt() {
    const created = await api.createAttempt(this.mode);
    if (!created.attemptToken) throw new Error("答题会话创建失败");
    this.applyAttempt(created.attemptToken, created.attempt, {});
  },

  async loadQuestions() {
    this.setData({ loading: true, result: null, answers: {}, currentIndex: 0, currentQuestion: null });
    const stored = api.getStoredAttempt(this.mode);
    try {
      if (stored) await this.restoreAttempt(stored);
      else await this.createAttempt();
    } catch (error) {
      api.clearStoredAttempt();
      try { await this.createAttempt(); }
      catch (createError) { wx.showToast({ title: createError.message || "题库加载失败", icon: "none" }); }
    } finally {
      this.setData({ loading: false });
    }
  },

  chooseAnswer(event) {
    const data = event.currentTarget.dataset;
    const answers = Object.assign({}, this.data.answers, { [data.id]: data.value });
    this.setData({ answers });
    if (this.attemptToken && this.attempt) api.saveStoredAttempt(this.attemptToken, this.attempt, answers);
    this.setCurrent(this.data.currentIndex);
  },

  previous() { this.setCurrent(this.data.currentIndex - 1); },
  next() { this.setCurrent(this.data.currentIndex + 1); },
  previewImage() {
    const url = this.data.currentQuestion.imageUrl;
    if (url) wx.previewImage({ current: url, urls: [url] });
  },
  previewReviewImage(event) {
    const url = event.currentTarget.dataset.url;
    if (url) wx.previewImage({ current: url, urls: [url] });
  },

  async submit() {
    const { questions, answers } = this.data;
    if (Object.keys(answers).length !== questions.length) {
      wx.showToast({ title: "请完成全部题目", icon: "none" });
      return;
    }
    this.setData({ submitting: true });
    try {
      const response = await api.submitAttempt(this.attemptToken, answers, this.displayName);
      response.details = formatQuestions(response.details, true, questions);
      response.wrongDetails = response.details.filter((item) => !item.isCorrect);
      this.setData({ result: response, currentIndex: 0 });
      api.clearStoredAttempt();
      this.setCurrent(0);
      wx.pageScrollTo({ scrollTop: 0, duration: 200 });
    } catch (error) {
      if ([401, 404, 410].includes(error.status)) {
        api.clearStoredAttempt();
        this.attemptToken = "";
      }
      wx.showToast({ title: error.message || "提交失败，请重试", icon: "none" });
    } finally {
      this.setData({ submitting: false });
    }
  },

  retry() {
    api.clearStoredAttempt();
    this.attemptToken = "";
    this.attempt = null;
    this.loadQuestions();
  },
});
