const api = require("../../services/api");

const DEFAULT_TITLE = "请选择以下日文对应的汉字字体";
const emptyForm = () => ({
  text: DEFAULT_TITLE, imageUrl: "", difficulty: 3, optionA: "", optionB: "",
  optionC: "", optionD: "", answer: "A", explanation: "",
});

function questionToForm(question) {
  return {
    text: question.text, imageUrl: question.imageUrl || "", difficulty: question.difficulty || 1,
    optionA: question.options[0], optionB: question.options[1], optionC: question.options[2],
    optionD: question.options[3], answer: question.answer, explanation: question.explanation || "",
  };
}

Page({
  data: { form: emptyForm(), saving: false, fontPresets: [], activeOption: "optionA" },

  onLoad(options) {
    this.adminToken = wx.getStorageSync(api.ADMIN_TOKEN_KEY);
    this.questionId = options.id || "";
    if (this.questionId) wx.setNavigationBarTitle({ title: "编辑题目" });
    this.loadFontPresets();
    if (this.questionId) this.loadQuestion();
  },

  async loadQuestion() {
    try {
      this.setData({ form: questionToForm(await api.getAdminQuestion(this.adminToken, this.questionId)) });
    } catch (error) { wx.showToast({ title: error.message || "题目加载失败", icon: "none" }); }
  },

  async loadFontPresets() {
    try { this.setData({ fontPresets: (await api.getAdminSettings(this.adminToken)).fontPresets }); }
    catch (error) { wx.showToast({ title: "字体快捷项加载失败", icon: "none" }); }
  },

  updateField(event) {
    const update = {};
    update[`form.${event.currentTarget.dataset.field}`] = event.detail.value;
    this.setData(update);
  },

  selectOption(event) { this.setData({ activeOption: event.currentTarget.dataset.field }); },
  insertPreset(event) {
    const update = {};
    update[`form.${this.data.activeOption}`] = event.currentTarget.dataset.value;
    this.setData(update);
  },
  selectAnswer(event) { this.setData({ "form.answer": event.detail.value }); },
  selectDifficulty(event) { this.setData({ "form.difficulty": Number(event.currentTarget.dataset.value) }); },

  async saveQuestion() {
    const { form } = this.data;
    const options = [form.optionA, form.optionB, form.optionC, form.optionD].map((item) => item.trim());
    if (!form.text.trim() || options.some((item) => !item) || !form.explanation.trim()) {
      wx.showToast({ title: "请填写题目、选项和解析", icon: "none" });
      return;
    }
    if (form.imageUrl && !/^https:\/\//i.test(form.imageUrl.trim())) {
      wx.showToast({ title: "题图链接必须使用 HTTPS", icon: "none" });
      return;
    }
    this.setData({ saving: true });
    const question = {
      text: form.text.trim(), imageUrl: form.imageUrl.trim(), difficulty: form.difficulty,
      options, answer: form.answer, explanation: form.explanation.trim(),
    };
    try {
      if (this.questionId) await api.updateAdminQuestion(this.adminToken, this.questionId, question);
      else await api.createAdminQuestion(this.adminToken, question);
      wx.showToast({ title: this.questionId ? "题目已更新" : "题目已加入题库", icon: "success" });
      setTimeout(() => wx.navigateBack(), 700);
    } catch (error) {
      wx.showToast({ title: error.message || "保存失败", icon: "none" });
    } finally { this.setData({ saving: false }); }
  },
});
